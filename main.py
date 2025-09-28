# budget_plus/main.py

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
import pandas as pd
from io import BytesIO
import logging
from typing import List, Dict, Tuple, Optional
import os
import tempfile

# --- รองรับทั้งรันแบบ "แพ็กเกจ" และ "ไฟล์เดี่ยวที่ราก" ---
try:
    # กรณีรันแบบแพ็กเกจ (uvicorn budget_plus.main:app)
    from .utils.number_format_utils import format_number
    from .pdf_summary import generate_pdf_default
    from .config import PERCENT_COLUMNS
    from .utils.variance_utils import calculate_variance, summarize_variance

    # Optional packs
    try:
        from .next_actions import suggest_as_dict  # Upgrade Pack (recommendations)
    except Exception:
        suggest_as_dict = None

    # ใช้เวอร์ชันใหม่ของ Excel Dashboard (v2)
    try:
        from .excel_dashboard_v2 import generate_excel_dashboard_v2
    except Exception:
        generate_excel_dashboard_v2 = None

    # เติมชีต Playbooks ลง Excel + คัดเลือก playbooks จาก YAML
    try:
        from .excel_playbooks_append import append_playbooks_sheet
        from .playbooks_loader import load_playbooks, select_playbooks
    except Exception:
        append_playbooks_sheet = None
        load_playbooks = select_playbooks = None

    # Router ชุด ZIP (PDF+Excel+Playbooks)
    try:
        from .report_exec_routes import router as report_exec_router
    except Exception:
        report_exec_router = None

except ImportError:  # กรณีรันจากราก repo (uvicorn main:app)
    from utils.number_format_utils import format_number
    from pdf_summary import generate_pdf_default
    from config import PERCENT_COLUMNS
    from utils.variance_utils import calculate_variance, summarize_variance

    try:
        from next_actions import suggest_as_dict
    except Exception:
        suggest_as_dict = None

    try:
        from excel_dashboard_v2 import generate_excel_dashboard_v2
    except Exception:
        generate_excel_dashboard_v2 = None

    try:
        from excel_playbooks_append import append_playbooks_sheet
        from playbooks_loader import load_playbooks, select_playbooks
    except Exception:
        append_playbooks_sheet = None
        load_playbooks = select_playbooks = None

    try:
        from report_exec_routes import router as report_exec_router
    except Exception:
        report_exec_router = None

app = FastAPI(title="Budget Plus Agent", version="1.2.0")
logging.basicConfig(level=logging.INFO)

# ====== Settings / Limits ======
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTS: Tuple[str, ...] = (".xlsx", ".xls")  # รองรับ Excel เท่านั้น

# ====== DataFrame normalization ======
REQUIRED_BASE_COLS: List[str] = ["Cost Center", "Planned"]

COLUMN_ALIASES: Dict[str, List[str]] = {
    "Cost Center": ["Cost Center", "CostCenter", "Cost_Center", "CC"],
    "Planned": ["Planned", "Plan", "Budget"],
    "Actual": ["Actual", "Actuals"],
    "FX Rate": ["FX Rate", "FXRate", "FX", "Rate"],
}

DERIVED_REQUIRED_COLS: List[str] = ["FX Adjusted Actual", "Variance"]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """ปรับชื่อคอลัมน์ให้เป็นชุดที่ระบบรู้จัก ตาม COLUMN_ALIASES"""
    rename_map: Dict[str, str] = {}
    for target, candidates in COLUMN_ALIASES.items():
        for c in candidates:
            if c in df.columns:
                rename_map[c] = target
                break
    return df.rename(columns=rename_map) if rename_map else df


def _ensure_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    - ต้องมี: 'Cost Center', 'Planned'
    - เติม 'Actual'=0 และ 'FX Rate'=1 ถ้าไม่มี
    - คำนวณ 'FX Adjusted Actual' และ 'Variance' ถ้ายังไม่มี
    """
    df = _normalize_columns(df)

    missing_base = [c for c in REQUIRED_BASE_COLS if c not in df.columns]
    if missing_base:
        raise HTTPException(
            status_code=400,
            detail=f"ขาดคอลัมน์จำเป็น: {missing_base}. คอลัมน์ที่พบ: {list(df.columns)}",
        )

    if "Actual" not in df.columns:
        df["Actual"] = 0
    if "FX Rate" not in df.columns:
        df["FX Rate"] = 1

    if "FX Adjusted Actual" not in df.columns:
        df["FX Adjusted Actual"] = df["Actual"] * df["FX Rate"]

    if "Variance" not in df.columns:
        # หากต้องการสลับทิศทาง ให้เปลี่ยนเป็น: df["FX Adjusted Actual"] - df["Planned"]
        df["Variance"] = df["Planned"] - df["FX Adjusted Actual"]

    missing_derived = [c for c in DERIVED_REQUIRED_COLS if c not in df.columns]
    if missing_derived:
        raise HTTPException(
            status_code=400,
            detail=f"ไม่สามารถคำนวณคอลัมน์ผลลัพธ์: {missing_derived}. คอลัมน์ที่พบ: {list(df.columns)}",
        )
    return df


async def _validate_and_read_excel(upload: UploadFile) -> pd.DataFrame:
    """ตรวจไฟล์ + อ่าน Excel เป็น DataFrame (async)"""
    filename = (upload.filename or "").lower()
    if not filename.endswith(ALLOWED_EXTS):
        raise HTTPException(
            status_code=400,
            detail=f"กรุณาอัปโหลดไฟล์ Excel นามสกุล {ALLOWED_EXTS}",
        )

    try:
        content = await upload.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"อ่านไฟล์ไม่สำเร็จ: {e}")

    if not content:
        raise HTTPException(status_code=400, detail="ไฟล์ว่างเปล่า")

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"ไฟล์ใหญ่เกินกำหนด ({len(content)/1024/1024:.2f} MB) - "
                f"จำกัด {MAX_UPLOAD_BYTES/1024/1024:.0f} MB"
            ),
        )

    try:
        df = pd.read_excel(BytesIO(content), engine="openpyxl")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"อ่านไฟล์ Excel ไม่สำเร็จ: {e}")

    if df is None or df.empty:
        raise HTTPException(status_code=400, detail="ไม่พบข้อมูลในไฟล์ (empty DataFrame)")
    return df


# ====== Routes ======

@app.get("/", response_class=HTMLResponse)
async def root():
    return (
        "<h3>✅ Budget Plus Agent is running.</h3>"
        "<p>POST to "
        "<code>/analyze</code>, <code>/download-report</code>, "
        "<code>/download-pdf</code>, <code>/analyze-suggest</code>, "
        "<code>/export-excel-exec</code>, <code>/report-exec</code>"
        "</p>"
    )


@app.get("/health")
async def health():
    return {"ok": True, "version": "1.2.0"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    df = await _validate_and_read_excel(file)

    try:
        df_ready = _ensure_required_columns(df)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"จัดรูปคอลัมน์ไม่สำเร็จ: {e}")

    try:
        df_calc = calculate_variance(df_ready)
        summary = summarize_variance(df_calc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"คำนวณสรุปไม่สำเร็จ: {e}")

    records = summary.to_dict(orient="records")
    for r in records:
        for col in ("Planned", "Actual", "FX Adjusted Actual", "Variance"):
            if col in r:
                r[col] = format_number(r[col], "number")
        for col in PERCENT_COLUMNS:
            if col in r:
                r[col] = format_number(r[col], "percent")
    return JSONResponse(content=records)


@app.post("/download-report")
async def download_report(file: UploadFile = File(...)):
    df = await _validate_and_read_excel(file)
    try:
        df_ready = _ensure_required_columns(df)
        df_calc = calculate_variance(df_ready)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"จัดรูป/คำนวณไม่สำเร็จ: {e}")

    buffer = BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df_calc.to_excel(writer, index=False, sheet_name="Report")
            wb = writer.book
            ws = writer.sheets["Report"]
            num_fmt = wb.add_format({"num_format": "#,##0.00"})
            pct_fmt = wb.add_format({"num_format": "0.00%"})
            num_cols = {"Planned", "Actual", "FX Adjusted Actual", "Variance"}
            for idx, col in enumerate(df_calc.columns):
                if col in num_cols:
                    ws.set_column(idx, idx, 15, num_fmt)
                elif col in PERCENT_COLUMNS:
                    ws.set_column(idx, idx, 15, pct_fmt)
                else:
                    ws.set_column(idx, idx, 15)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"สร้าง Excel ไม่สำเร็จ: {e}")

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=budget_plus_report.xlsx"},
    )


@app.post("/download-pdf")
async def download_pdf(file: UploadFile = File(...)):
    df = await _validate_and_read_excel(file)
    try:
        df_ready = _ensure_required_columns(df)
        df_calc = calculate_variance(df_ready)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"จัดรูป/คำนวณไม่สำเร็จ: {e}")

    try:
        pdf_buffer = generate_pdf_default(df_calc)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"สร้าง PDF ไม่สำเร็จ: {e}")

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=budget_plus_report.pdf"},
    )


# ====== NEW: Analyze + Next Action Recommender (JSON) ======
@app.post("/analyze-suggest")
async def analyze_suggest(file: UploadFile = File(...)):
    if suggest_as_dict is None:
        raise HTTPException(
            status_code=501,
            detail="ไม่พบโมดูล next_actions.py (Upgrade Pack). โปรดติดตั้งก่อนใช้งาน /analyze-suggest"
        )

    df = await _validate_and_read_excel(file)
    try:
        df_ready = _ensure_required_columns(df)
        df_calc = calculate_variance(df_ready)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"จัดรูป/คำนวณไม่สำเร็จ: {e}")

    try:
        result = suggest_as_dict(df_calc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"วิเคราะห์/แนะนำถัดไปไม่สำเร็จ: {e}")

    return JSONResponse(content=result)


# ====== NEW: Export Executive Dashboard (Excel v2 + Next Actions + Playbooks) ======
@app.post("/export-excel-exec")
async def export_excel_exec(file: UploadFile = File(...)):
    if generate_excel_dashboard_v2 is None:
        raise HTTPException(
            status_code=501,
            detail="ไม่พบโมดูล excel_dashboard_v2.py. โปรดติดตั้งก่อนใช้งาน /export-excel-exec"
        )

    df = await _validate_and_read_excel(file)
    try:
        df_ready = _ensure_required_columns(df)
        df_calc = calculate_variance(df_ready)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"จัดรูป/คำนวณไม่สำเร็จ: {e}")

    actions: Optional[Dict] = None
    if suggest_as_dict is not None:
        try:
            actions = suggest_as_dict(df_calc)
        except Exception:
            actions = None

    # สร้าง Excel แล้ว (ถ้ามี) เติมชีต Playbooks
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            temp_path = tmp.name

        # เลือกมิติเล่าเรื่องตามลำดับความสำคัญ (แก้ได้)
        generate_excel_dashboard_v2(
            df_calc,
            temp_path,
            next_actions=actions,
            dim_priority=["Category", "Department", "Region", "Product", "Customer", "Cost Center"],
            top_n=10
        )

        # เติมชีต Playbooks หากมีโมดูลและ YAML พร้อม
        if append_playbooks_sheet and load_playbooks and select_playbooks and actions:
            # ค้นหาโฟลเดอร์ playbooks ได้ทั้งแบบแพ็กเกจและราก
            base_dir = os.path.dirname(__file__) if "__file__" in globals() else "."
            pb_dir = os.path.join(base_dir, "playbooks")
            if not os.path.isdir(pb_dir):
                pb_dir = "playbooks"
            if os.path.isdir(pb_dir):
                pbs_all = load_playbooks(pb_dir)
                selected = select_playbooks(pbs_all, actions.get("summary", {}))
                if selected:
                    append_playbooks_sheet(temp_path, selected)

        # อ่านกลับเป็น bytes แล้วลบทิ้ง
        with open(temp_path, "rb") as f:
            data = f.read()
        os.remove(temp_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"สร้าง Executive Dashboard Excel ไม่สำเร็จ: {e}")

    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Executive_Dashboard.xlsx"},
    )


# ====== Include /report-exec router (ZIP: PDF + Excel + Playbooks) ======
if report_exec_router is not None:
    app.include_router(report_exec_router)
