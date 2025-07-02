from fastapi import APIRouter, UploadFile, File
router = APIRouter()
@router.post("/analyze")
async def analyze_plus(file: UploadFile = File(...)):
    return {"tier": "plus", "status": "processed"}
