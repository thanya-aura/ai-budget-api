
"""
pdf_enhancements_alerts.py
Draw a "Scenarios & Alerts" section into the PDF report.
"""

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

def draw_scenarios_alerts_page(c: "canvas.Canvas", scenarios: dict, alerts: dict):
    width, height = A4
    x0, y = 2*cm, height - 2*cm
    lh = 14

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x0, y, "Scenarios & Alerts")
    y -= 22

    # Scenarios summary
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x0, y, "Scenario Impacts"); y -= lh
    c.setFont("Helvetica", 11)
    base_plan = scenarios.get("summary", {}).get("base_planned", 0)
    base_var = scenarios.get("summary", {}).get("base_variance", 0)
    c.drawString(x0, y, f"Base: Plan={base_plan:,.0f}, Variance={base_var:,.0f}"); y -= lh

    for sc in scenarios.get("scenarios", [])[:8]:
        name = sc.get("name","")
        var = sc.get("total_variance", 0.0)
        delta = sc.get("delta_vs_base", 0.0)
        c.drawString(x0+10, y, f"- {name}: Var={var:,.0f} (Δ vs base: {delta:,.0f})")
        y -= lh
        if y < 2*cm:
            c.showPage(); y = height - 2*cm

    y -= 6
    if y < 2*cm:
        c.showPage(); y = height - 2*cm

    # Alerts section
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x0, y, "Alerts (Rolling 3M > 8%)"); y -= lh
    c.setFont("Helvetica", 11)

    crossings = alerts.get("crossings", [])
    if not crossings:
        note = alerts.get("note", "No crossings detected or missing Month column.")
        for chunk in _wrap(note, 100):
            c.drawString(x0, y, chunk); y -= lh
            if y < 2*cm: c.showPage(); y = height - 2*cm
    else:
        for rec in crossings[:12]:
            c.drawString(x0+10, y, f"- {rec.get('month','')}: ratio={rec.get('ratio',0):.2f} → {rec.get('note','')}")
            y -= lh
            if y < 2*cm: c.showPage(); y = height - 2*cm
