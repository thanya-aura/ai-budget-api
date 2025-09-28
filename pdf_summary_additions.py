# budget_plus/pdf_summary_additions.py
from typing import Dict, List
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors

def _wrap(text: str, width: int = 100) -> List[str]:
    words = text.split()
    line, n, out = [], 0, []
    for w in words:
        n += len(w) + 1
        line.append(w)
        if n >= width:
            out.append(" ".join(line)); line, n = [], 0
    if line:
        out.append(" ".join(line))
    return out

def draw_next_actions_page(c: "canvas.Canvas", actions_result: Dict):
    """วาดหน้า Next Actions แบบสวยอ่านง่าย"""
    width, height = A4
    x0, y = 2 * cm, height - 2 * cm
    lh = 14

    c.setFont("Helvetica-Bold", 16)
    c.drawString(x0, y, "Next Actions")
    y -= 22

    items = actions_result.get("next_actions", []) or []
    if not items:
        c.setFont("Helvetica", 11)
        c.drawString(x0, y, "No recommendations available.")
        return

    for idx, act in enumerate(items, start=1):
        title = act.get("title", "")
        rationale = act.get("rationale", "")
        how = act.get("how_to", [])
        outcome = act.get("expected_outcome", "")

        # Card frame
        top_y = y
        card_h = 0  # dynamic; we draw border after text ifต้องการ

        # Title
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#333333"))
        c.drawString(x0, y, f"{idx}. {title}")
        y -= lh

        # Why
        c.setFont("Helvetica", 11)
        c.setFillColor(colors.HexColor("#555555"))
        for chunk in _wrap(f"Why: {rationale}", 100):
            c.drawString(x0, y, chunk); y -= lh
            if y < 2 * cm: c.showPage(); y = height - 2 * cm

        # How-to steps
        c.setFillColor(colors.black)
        for step in (how or []):
            for chunk in _wrap(f"- {step}", 96):
                c.drawString(x0 + 12, y, chunk); y -= lh
                if y < 2 * cm: c.showPage(); y = height - 2 * cm

        # Expected outcome
        if outcome:
            c.setFillColor(colors.HexColor("#555555"))
            for chunk in _wrap(f"Outcome: {outcome}", 100):
                c.drawString(x0, y, chunk); y -= lh
                if y < 2 * cm: c.showPage(); y = height - 2 * cm

        # spacing between cards
        y -= 8
        if y < 2 * cm:
            c.showPage()
            y = height - 2 * cm

        c.setFillColor(colors.black)
