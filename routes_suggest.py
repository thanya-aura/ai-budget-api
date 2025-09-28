
"""
Drop-in FastAPI router that adds /analyze-suggest endpoint.
Assumes the main app uses pandas DataFrames similar to budget_plus.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
from io import BytesIO

# Import from local package if available
try:
    from .utils.variance_utils import calculate_variance
except Exception:
    # fallback for repo-root run
    from utils.variance_utils import calculate_variance

try:
    from .next_actions import suggest_as_dict
except Exception:
    from next_actions import suggest_as_dict

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB

@router.post("/analyze-suggest")
async def analyze_suggest(file: UploadFile = File(...)):
    if file.content_type not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "text/csv"]:
        raise HTTPException(status_code=400, detail="รองรับเฉพาะ Excel/CSV")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="ไฟล์ใหญ่เกินไป")

    # Load DataFrame
    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(BytesIO(content))
        else:
            df = pd.read_excel(BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"อ่านไฟล์ไม่สำเร็จ: {e}")

    # Normalize expected columns
    for col in ["Planned", "Actual"]:
        if col not in df.columns:
            raise HTTPException(status_code=400, detail=f"ไม่พบคอลัมน์ {col}")

    df_calc = calculate_variance(df)
    result = suggest_as_dict(df_calc)

    return JSONResponse(result)
