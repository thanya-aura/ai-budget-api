# budget_plus/main.py

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
import pandas as pd
from io import BytesIO
import logging
from typing import List, Dict

# --- imports (รันแบบแพ็กเกจ) ---
from .utils.number_format_utils import format_number
from .pdf_summary import generate_pdf_default
from .config import PERCENT_COLUMNS
from .utils.variance_utils import calculate_variance, summarize_variance

app = FastAPI(title="Budget Plus Agent", version="1.0.0")
logging.basicConfig(level=logging.INFO)

# ====== Settings / Limits ======
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTS = (".xlsx", ".xls")     # รองรับ Excel เท่านั้น

# ====== ส่วนช่วยเตรียม DataFrame ให้อยู่ในรูปที่ระบบต้องการ ======

# ชุดคอลัมน์ขั้นต่ำที่ "ต้องมีจริง" เพื่อคำนวณ/สร้างรายงานได้
REQUIRED_BASE_COLS: List[str] = ["Cost Center", "Planned"]

# ชื่อคอลัมน์ที่ระบบรู้จัก และชื่อที่มักพบบนไฟล์ของผู้ใช้ (alias)
COLUMN_ALIASES: Dict[str, List[str]] = {
    "Cost Center": ["Cost Center", "CostCenter", "Cost_Center", "CC"],
    "Planned": ["Planned", "Plan", "Budget"],

    # ใช้เพื่อคำนวณ FX Adjusted Actual/Variance ถ้ายังไม่มี
    "Actual": ["Actual", "Actuals"],
    "FX Rate": ["FX Rate", "FXRate", "FX", "Rate"],
}

# คอลัมน์ผลลัพธ์ที่ endpoint ของเราคาดหวังเมื่อจะสร้างสรุป/รายงาน
DERIVED_REQUIRED_COLS: List[str] = [
    "FX Adjusted Actual",  # = Actual * FX Rate (ถ้ามี FX Rate), ไม่งั้น = Actual
    "Variance",            # = Planned - FX Adjusted Actual
]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """ปรับชื่อคอลัมน์ให้เป็นชุดที่ระบบรู้จัก ตาม COLUMN_ALIASES"""
    rename_map: Dict[str, str] = {}
    for target, candidates in COLUMN_ALIASES.items():
        for c in candidates:
            if c in df.columns:
                rename_map[c] = target
                break
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def _ensure_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    - บังคับให้มีคอลัมน์พื้นฐาน: 'Cost Center', 'Planned'
    - เติม 'Actual' และ 'FX Rate' ถ้าไม่มี (Actual=0, FX Rate=1)
    - คำนวณ 'FX Adjusted Actual' และ 'Variance' ถ้าไม่มี
    """
    df = _normalize_columns(df)

    # ตรวจ base cols
    missing_base = [c for c in REQUIRED_BASE_COLS if c not in df.columns]
    if missing_base:
        raise HTTPException(
            status_code=400,
            detail=f"ขาดคอลัมน์จำเป็น: {missing_base}. คอลัมน์ที่พบ: {list(df.columns)}",
        )

    # เติมคอลัมน์ช่วยคำนวณ
    if "Actual" not in df.columns:
        df["Actual"] = 0
    if "FX Rate" not in df.columns:
        df["FX Rate"] = 1

    # คำนวณคอลัมน์ที่ระบบต้องใช้ต่อไป
    if "FX Adjusted Actual" not in df.columns:
        df["FX Adjusted Actual"] = df["Actual"] * df["FX Rate"]

    if "Variance" not in df.columns:
        df["Variance"] = df["Planned"] - df["FX Adjusted Actual"]

    # เช็กให้ชัวร์ว่ามีทั้ง 2 คอลัมน์แล้ว
    missing_derived = [c for c in DERIVED_REQUIRED_COLS if c not in df.columns]
    if missing_derived:
        raise HTTPException(
            status_code=400,
            detail=f"ไม่สามารถคำนวณคอลัมน์ผลลัพธ์: {missing_derived}. คอลัมน์ที่พบ: {list(df.columns)}",
        )

    return df


def _validate_and_read_excel(upload: UploadFile) -> pd.DataFrame:
    """ตรวจชนิดไฟล์/ขนาด แล้วอ่าน Excel เป็น DataFrame ด้วย openpyxl"""
    # 1) เช็กนามสกุลไฟล์
    filename = (upload.filename or "").lower()
    if not filename.endswith(ALLOWED_EXTS):
        raise HTTPException(
            status_code=400,
            detail=f"กรุณาอัปโหลดไฟล์ Excel นามสกุล {ALLOWED_EXTS}",
        )

    # 2) อ่านเนื้อหา + เช็กขนาด
    try:
        content = upload.file.read()
    except Exception as e:
        # กรณีบาง client ใช้ .file ไม่ได้ ให้ fallback ไปใช้ await file.read()
        # แต่ endpoint ของเราประกาศ async อยู่แล้ว—สำหรับปลอดภัยลองอ่านซ้ำแบบ async หากจำเป็น
        # อย่างไรก็ดี Render/UVicorn ส่วนใหญ่รับได้จาก .file.read() ตรง ๆ
        raise HTTPException(status_code=400, detail=f"อ่านไฟล์ไม่สำเร็จ: {e}")

    if not content:
        raise HTTPException(status_code=400, detail="ไฟล์ว่างเปล่า")

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,  # Payload Too Large
            detail=f"ไฟล์ใหญ่เกินกำหนด ({len(content)/1024/1024:.2f} MB) - จำกัด {MAX_UPLOAD_BYTES/1024/1024:.0f} MB",
        )

    # 3) แปลงเป็น DataFrame
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
    # อ่านไฟล์
    df = _validate_and_read_excel(file)

    # เตรียมคอลัมน์ให้อยู่ในรูปที่ระบบต้องการ
    try:
        df_ready = _ensure_required_columns(df)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"จัดรูปคอลัมน์ไม่สำเร็จ: {e}")

    # คำนวณเชิงธุรกิจ (numeric)
    try:
        df_calc = calculate_variance(df_ready)
        summary = summarize_variance(df_calc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"คำนวณสรุปไม่สำเร็จ: {e}")

    # จัดรูปสำหรับ output (format เฉพาะตอนส่งออก)
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
    # อ่านไฟล์
    df = _validate_and_read_excel(file)

    # เตรียมคอลัมน์ + คำนวณ
    try:
        df_ready = _ensure_required_columns(df)
        df_calc = calculate_variance(df_ready)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"จัดรูป/คำนวณไม่สำเร็จ: {e}")

    # สร้างไฟล์ Excel พร้อมฟอร์แมต
    buffer = BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df_calc.to_excel(writer, index=False, sheet_name="Report")

            workbook = writer.book
            worksheet = writer.sheets["Report"]

            number_fmt = workbook.add_format({"num_format": "#,##0.00"})
            percent_fmt = workbook.add_format({"num_format": "0.00%"})

            num_cols = {"Planned", "Actual", "FX Adjusted Actual", "Variance"}
            for idx, col in enumerate(df_calc.columns):
                if col in num_cols:
                    worksheet.set_column(idx, idx, 15, number_fmt)
                elif col in PERCENT_COLUMNS:
                    worksheet.set_column(idx, idx, 15, percent_fmt)
                else:
                    worksheet.set_column(idx, idx, 15)
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
    # อ่านไฟล์
    df = _validate_and_read_excel(file)

    # เตรียมคอลัมน์ + คำนวณ
    try:
        df_ready = _ensure_required_columns(df)
        df_calc = calculate_variance(df_ready)  # ทำ numeric ให้ครบก่อนสรุป
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"จัดรูป/คำนวณไม่สำเร็จ: {e}")

    # สร้าง PDF
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
