
"""
report_playbooks_pdf.py
Generate a standalone PDF listing selected playbooks.
"""

from io import BytesIO
from typing import List, Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

def _wrap(text, width=100):
    words = text.split()
    line, n = [], 0
    for w in words:
        n += len(w) + 1
        line.append(w)
        if n >= width:
            yield " ".join(line); line, n = [], 0
    if line:
        yield " ".join(line)

def generate_playbooks_pdf(playbooks: List[Dict[str, Any]]) -> BytesIO:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    x0, y = 2*cm, height - 2*cm
    lh = 14

    c.setFont("Helvetica-Bold", 16)
    c.drawString(x0, y, "Executive Playbooks")
    y -= 22

    for pb in playbooks:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x0, y, f"{pb.get('id','')}: {pb.get('title','')}")
        y -= lh

        c.setFont("Helvetica", 11)
        for chunk in _wrap(f"Why: {pb.get('rationale','')}", 100):
            c.drawString(x0, y, chunk); y -= lh
            if y < 2*cm: c.showPage(); y = height - 2*cm

        for step in pb.get("steps", []):
            for chunk in _wrap(f"- {step}", 100):
                c.drawString(x0+10, y, chunk); y -= lh
                if y < 2*cm: c.showPage(); y = height - 2*cm

        if pb.get("expected_outcome"):
            for chunk in _wrap(f"Outcome: {pb['expected_outcome']}", 100):
                c.drawString(x0, y, chunk); y -= lh
                if y < 2*cm: c.showPage(); y = height - 2*cm

        y -= 6
        if y < 2*cm: c.showPage(); y = height - 2*cm

    c.showPage(); c.save(); buf.seek(0)
    return buf
