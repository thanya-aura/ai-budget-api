# Budget Plus Agent

FastAPI บริการสรุปงบประมาณ + สร้างรายงาน **Excel/PDF** พร้อมกราฟ

## Quick start
```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn budget_plus.main:app --host 127.0.0.1 --port 8000 --reload
