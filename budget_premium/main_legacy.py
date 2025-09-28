from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
import pandas as pd
from io import BytesIO
from modules.dashboard_generator import generate_pdf_summary
from modules.reallocation_ai import suggest_reallocation
from modules.accuracy_score import compute_accuracy_score
from modules.driver_forecasting import forecast_from_drivers
from modules.audit_log import log_changes
from modules.access_control import check_access
from modules.scenario_engine import apply_scenarios
from modules.versioning import compare_versions
from modules.erp_sync import export_to_erp_format

app = FastAPI(title="Budget Premium Agent (Full)", version="3.0")

@app.post("/analyze")
async def analyze(file: UploadFile = File(...), user_role: str = "editor"):
    check_access(user_role, action="analyze")
    contents = await file.read()
    df = pd.read_excel(BytesIO(contents))
    df["Adjusted Actual"] = df["Actual"] * df["FX Rate"]
    df["Variance"] = df["Adjusted Actual"] - df["Planned"]
    df["Accuracy Score"] = compute_accuracy_score(df)
    df["Reallocation Advice"] = df.apply(suggest_reallocation, axis=1)
    df = apply_scenarios(df)
    log_changes(df)
    df = forecast_from_drivers(df)
    return JSONResponse(content=df.to_dict(orient="records"))

@app.post("/download-report")
async def download_report(file: UploadFile = File(...)):
    contents = await file.read()
    df = pd.read_excel(BytesIO(contents))
    df["Adjusted Actual"] = df["Actual"] * df["FX Rate"]
    df["Variance"] = df["Adjusted Actual"] - df["Planned"]
    df["Accuracy Score"] = compute_accuracy_score(df)
    df["Reallocation Advice"] = df.apply(suggest_reallocation, axis=1)
    df = apply_scenarios(df)
    df = forecast_from_drivers(df)
    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=processed_report.xlsx"})

@app.post("/download-pdf")
async def download_pdf(file: UploadFile = File(...)):
    contents = await file.read()
    df = pd.read_excel(BytesIO(contents))
    df["Adjusted Actual"] = df["Actual"] * df["FX Rate"]
    df["Variance"] = df["Adjusted Actual"] - df["Planned"]
    pdf = generate_pdf_summary(df)
    return StreamingResponse(pdf, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=budget_summary.pdf"})