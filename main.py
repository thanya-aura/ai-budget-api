from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
import pandas as pd
from io import BytesIO
import logging

# ✅ relative imports ภายในแพ็กเกจ budget_plus
from .utils.number_format_utils import format_number
from .pdf_summary import generate_pdf_default
from .config import PERCENT_COLUMNS
from .utils.variance_utils import calculate_variance, summarize_variance

app = FastAPI(title="Budget Plus Agent", version="1.0.0")

logging.basicConfig(level=logging.INFO)


@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h3>✅ Budget Plus Agent is running. POST to /analyze, /download-report, or /download-pdf</h3>"


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    contents = await file.read()
    df = pd.read_excel(BytesIO(contents))

    required = {"Version", "Scenario", "Cost Center", "Planned", "Actual"}
    if missing := required - set(df.columns):
        raise HTTPException(status_code=400, detail=f"Missing: {', '.join(missing)}")

    # คำนวณแบบ numeric ภายใน
    df = calculate_variance(df)
    summary = summarize_variance(df)

    # แปลงเป็น string เฉพาะผลลัพธ์ส่งออก
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
    contents = await file.read()
    df = pd.read_excel(BytesIO(contents))

    # คำนวณ numeric
    df = calculate_variance(df)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Report")

        workbook = writer.book
        worksheet = writer.sheets["Report"]

        number_fmt = workbook.add_format({"num_format": "#,##0.00"})
        percent_fmt = workbook.add_format({"num_format": "0.00%"})

        # ✅ จัด format ให้ถูกคอลัมน์ (เลข / เปอร์เซ็นต์)
        num_cols = {"Planned", "Actual", "FX Adjusted Actual", "Variance"}
        for idx, col in enumerate(df.columns):
            if col in num_cols:
                worksheet.set_column(idx, idx, 15, number_fmt)
            elif col in PERCENT_COLUMNS:
                worksheet.set_column(idx, idx, 15, percent_fmt)
            else:
                worksheet.set_column(idx, idx, 15)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=budget_plus_report.xlsx"}
    )


@app.post("/download-pdf")
async def download_pdf(file: UploadFile = File(...)):
    contents = await file.read()
    df = pd.read_excel(BytesIO(contents))

    df = calculate_variance(df)  # numeric
    pdf_buffer = generate_pdf_default(df)

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=budget_plus_report.pdf"}
    )
