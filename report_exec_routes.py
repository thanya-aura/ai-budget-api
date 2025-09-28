
"""
report_exec_routes.py
Expose POST /report-exec to produce a ZIP bundle:
- Executive_Dashboard.xlsx (with Playbooks sheet)
- Budget_Executive_Report.pdf (your main PDF from generate_pdf_default)
- Executive_Playbooks.pdf (playbooks-only appendix)
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
import pandas as pd
import zipfile, os, tempfile

# Import from local package if available
try:
    from .utils.variance_utils import calculate_variance
    from .pdf_summary import generate_pdf_default
except Exception:
    from utils.variance_utils import calculate_variance
    from pdf_summary import generate_pdf_default

try:
    from .next_actions import suggest_as_dict
except Exception:
    from next_actions import suggest_as_dict

try:
    from .excel_dashboard import generate_excel_dashboard
except Exception:
    from excel_dashboard import generate_excel_dashboard

try:
    from .playbooks_loader import load_playbooks, select_playbooks
except Exception:
    from playbooks_loader import load_playbooks, select_playbooks

try:
    from .excel_playbooks_append import append_playbooks_sheet
except Exception:
    from excel_playbooks_append import append_playbooks_sheet

try:
    from .report_playbooks_pdf import generate_playbooks_pdf
except Exception:
    from report_playbooks_pdf import generate_playbooks_pdf

router = APIRouter()

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB

@router.post("/report-exec")
async def report_exec(file: UploadFile = File(...)):
    if file.content_type not in [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel"
    ]:
        raise HTTPException(status_code=400, detail="รองรับเฉพาะไฟล์ Excel")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="ไฟล์ใหญ่เกินไป")

    # Read dataframe
    try:
        df = pd.read_excel(BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"อ่านไฟล์ไม่สำเร็จ: {e}")

    # Compute
    df_calc = calculate_variance(df)
    actions = suggest_as_dict(df_calc)

    # Select playbooks
    pb_dir = os.path.join(os.path.dirname(__file__), "playbooks")
    if not os.path.isdir(pb_dir):
        pb_dir = "playbooks"  # fallback to CWD
    pbs_all = load_playbooks(pb_dir)
    selected = select_playbooks(pbs_all, actions.get("summary", {}))

    # Build outputs
    # 1) Excel dashboard (then append "Playbooks" sheet)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        excel_path = tmp.name
    generate_excel_dashboard(df_calc, excel_path, actions, top_n=10)
    if selected:
        append_playbooks_sheet(excel_path, selected)
    with open(excel_path, "rb") as f:
        excel_bytes = f.read()
    os.remove(excel_path)

    # 2) Main PDF report
    pdf_buf = generate_pdf_default(df_calc)
    pdf_bytes = pdf_buf.read()

    # 3) Playbooks PDF appendix
    pb_pdf_buf = generate_playbooks_pdf(selected)
    pb_pdf_bytes = pb_pdf_buf.read()

    # Zip bundle
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Executive_Dashboard.xlsx", excel_bytes)
        z.writestr("Budget_Executive_Report.pdf", pdf_bytes)
        z.writestr("Executive_Playbooks.pdf", pb_pdf_bytes)
        # plus a JSON manifest
        import json
        manifest = {
            "counts": {"playbooks": len(selected)},
            "playbooks": [{"id": p.get("id"), "title": p.get("title")} for p in selected]
        }
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    zip_buf.seek(0)

    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=Executive_Report_Bundle.zip"},
    )
