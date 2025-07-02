from fastapi import APIRouter, UploadFile, File
router = APIRouter()
@router.post("/analyze")
async def analyze_premium(file: UploadFile = File(...)):
    return {"tier": "premium", "status": "processed"}
