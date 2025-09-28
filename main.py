# budget_plus/main.py

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
import pandas as pd
from io import BytesIO
import logging
from typing import List, Dict, Tuple

# --- รองรับทั้งรันแบบ "แพ็กเกจ" และ "ไฟล์เดี่ยวที่ราก" ---
try:
    # กรณีรันแบบแพ็กเกจ (uvicorn budget_plus.main:app)
    from .utils.number_format_utils import format_number
    from .pdf_summary import generate_pdf_default
    from .config import PERCENT_COLUMNS
    from .utils.variance_utils import calculate_variance, summarize_variance
except ImportError:  # กรณีรันจากราก repo (uvicorn main:app)
    from utils.number_format_utils import format_number
    from pdf_summary import generate_pdf_default
    from config import PERCENT_COLUMNS
    from utils.variance_utils import calculate_variance, summarize_variance

app = FastAPI(title="Budget Plus Agent", version="1.0.0")
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
            status_code=413,  # Payload Too Large
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
    return "<h3>✅ Budget Plus Agent is running. POST to /analyze, /download-report, or /download-pdf</h3>"


@app.get("/health")
async def health():
    return {"ok": True, "version": "1.0.0"}


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
