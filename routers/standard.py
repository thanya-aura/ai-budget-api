from fastapi import APIRouter, UploadFile, File
router = APIRouter()
@router.post("/analyze")
async def analyze_standard(file: UploadFile = File(...)):
    return {"tier": "standard", "status": "processed"}
