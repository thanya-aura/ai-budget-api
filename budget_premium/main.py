# budget_premium/main.py
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import pandas as pd
from io import BytesIO

# ใช้ import แบบระบุแพ็กเกจ (ต้องมี __init__.py ใน budget_premium และ modules)
from budget_premium.modules.number_format import apply_scale_series
from budget_premium.modules.display_utils import add_formatted_columns
from budget_premium.modules.next_action import recommend_next_actions
from budget_premium.modules.pdf_dashboard import generate_pdf_dashboard
from budget_premium.modules.excel_dashboard import generate_excel_dashboard

app = FastAPI(title="Budget Premium Agent (Upgraded)", version="3.1")

ALLOWED_SCALES = ["raw", "k", "m"]


def _read_excel_from_upload(file_bytes: bytes) -> pd.DataFrame:
    """อ่านไฟล์ Excel จาก UploadFile ให้เป็น DataFrame"""
    try:
        return pd.read_excel(BytesIO(file_bytes), engine="openpyxl")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Excel file: {e}")


def _compute_base_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    คำนวณคอลัมน์พื้นฐานที่โปรเจกต์ใช้อยู่:
      Adjusted Actual = Actual * FX Rate
      Variance = Adjusted Actual - Planned
    (จะคำนวณเฉพาะเมื่อคอลัมน์ที่ต้องใช้มีครบ)
    """
    out = df.copy()
    cols = {"Actual", "FX Rate", "Planned"}
    if cols.issubset(out.columns):
        out["Adjusted Actual"] = out["Actual"] * out["FX Rate"]
        out["Variance"] = out["Adjusted Actual"] - out["Planned"]
    return out


@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version}


@app.post("/process")
async def process(
    file: UploadFile = File(...),
    scale: str = Query("raw", enum=ALLOWED_SCALES),
    money_decimals: int = 2,
    pct_decimals: int = 2,
):
    contents = await file.read()
    df = _read_excel_from_upload(contents)
    df = _compute_base_columns(df)

    # สร้างคอลัมน์สำหรับ “แสดงผล” โดยไม่กระทบค่าจริง
    display = add_formatted_columns(
        df,
        money_cols=[c for c in ["Planned", "Actual", "Adjusted Actual", "Variance"] if c in df.columns],
        pct_cols=[c for c in ["Growth", "Margin %", "YoY %"] if c in df.columns],
        scale=scale,
        decimals=money_decimals,
        pct_decimals=pct_decimals,
    )

    # คำแนะนำถัดไป (rule-based)
    recs = recommend_next_actions(df)

    # ตัดให้ไม่ยาวเกินไป
    preview = display.head(50).to_dict(orient="records")
    return JSONResponse({"preview": preview, "next_actions": recs})


@app.post("/download-excel")
async def download_excel(
    file: UploadFile = File(...),
    scale: str = Query("raw", enum=ALLOWED_SCALES),
):
    contents = await file.read()
    df = _read_excel_from_upload(contents)
    df = _compute_base_columns(df)

    excel_io = generate_excel_dashboard(df, scale=scale)

    filename = f"executive_dashboard_{scale}.xlsx"
    return StreamingResponse(
        excel_io,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.post("/download-pdf")
async def download_pdf(
    file: UploadFile = File(...),
    scale: str = Query("raw", enum=ALLOWED_SCALES),
    money_decimals: int = 2,
):
    contents = await file.read()
    df = _read_excel_from_upload(contents)
    df = _compute_base_columns(df)

    pdf_io = generate_pdf_dashboard(df, scale=scale, decimals=money_decimals)

    filename = f"executive_dashboard_{scale}.pdf"
    return StreamingResponse(
        pdf_io,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

