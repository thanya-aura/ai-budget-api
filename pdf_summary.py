# pdf_summary.py

# ใช้ backend ที่ไม่ต้องมีจอ (สำหรับ Render/Server)
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import cm
from reportlab.lib import colors

# --- รองรับทั้งรันแบบ "แพ็กเกจ" และ "ไฟล์เดี่ยวที่ราก" ---
try:
    # กรณีรันแบบแพ็กเกจ (uvicorn budget_plus.main:app)
    from .utils.number_format_utils import format_number
    from .config import PERCENT_COLUMNS
except ImportError:
    # กรณีรันแบบ root module (uvicorn main:app)
    from utils.number_format_utils import format_number
    from config import PERCENT_COLUMNS

# ========== Next Actions ==========
try:
    from .next_actions import suggest_as_dict
except Exception:
    try:
        from next_actions import suggest_as_dict
    except Exception:
        # fallback ดัมมี (กันล่ม) ถ้าไม่มีโมดูลจริง
        def suggest_as_dict(df):
            return {
                "summary": {},
                "next_actions": [
                    {
                        "title": "Add Upgrade Pack",
                        "rationale": "ไม่พบโมดูล next_actions.py",
                        "how_to": ["คัดลอก next_actions.py เข้าสู่ budget_plus/ แล้วรันใหม่"],
                        "expected_outcome": "ระบบแนะนำ Next Actions อัตโนมัติ",
                        "tags": ["setup"]
                    }
                ],
                "drilldowns": {}
            }

# ========== Scenarios & Alerts ==========
# คำนวณ scenarios/alerts
try:
    from .scenarios_alerts import compute_scenarios, scan_alerts
except Exception:
    try:
        from scenarios_alerts import compute_scenarios, scan_alerts
    except Exception:
        def compute_scenarios(df):
            # fallback เบาๆ ถ้าไม่มีโมดูลจริง
            base_plan = float(df.get("Planned", 0).sum()) if "Planned" in df.columns else 0.0
            base_actual_fx = float(df.get("FX Adjusted Actual", 0).sum()) if "FX Adjusted Actual" in df.columns else 0.0
            base_var = base_actual_fx - base_plan
            return {"summary": {"base_planned": base_plan, "base_actual_fx": base_actual_fx, "base_variance": base_var}, "scenarios": []}
        def scan_alerts(df, pct_threshold: float = 0.08):
            return {"series": [], "crossings": [], "note": "Scenarios/Alerts module missing."}

# วาดหน้า scenarios/alerts
try:
    from .pdf_enhancements_alerts import draw_scenarios_alerts_page
except Exception:
    try:
        from pdf_enhancements_alerts import draw_scenarios_alerts_page
    except Exception:
        # fallback วาดหน้าแบบเรียบง่าย
        def _wrap_sa(text, width=100):
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
            c.setFont("Helvetica-Bold", 16); c.drawString(x0, y, "Scenarios & Alerts"); y -= 22
            c.setFont("Helvetica-Bold", 12); c.drawString(x0, y, "Scenario Impacts"); y -= lh
            c.setFont("Helvetica", 11)
            bp = scenarios.get("summary", {}).get("base_planned", 0)
            bv = scenarios.get("summary", {}).get("base_variance", 0)
            c.drawString(x0, y, f"Base: Plan={bp:,.0f}, Variance={bv:,.0f}"); y -= lh
            for sc in scenarios.get("scenarios", [])[:8]:
                c.drawString(x0+10, y, f"- {sc.get('name','')}: Var={sc.get('total_variance',0):,.0f} (Δ {sc.get('delta_vs_base',0):,.0f})")
                y -= lh
                if y < 2*cm: c.showPage(); y = height - 2*cm
            y -= 6
            c.setFont("Helvetica-Bold", 12); c.drawString(x0, y, "Alerts (Rolling 3M > 8%)"); y -= lh
            c.setFont("Helvetica", 11)
            crosses = alerts.get("crossings", [])
            if not crosses:
                for chunk in _wrap_sa(alerts.get("note", "No crossings detected."), 100):
                    c.drawString(x0, y, chunk); y -= lh
                    if y < 2*cm: c.showPage(); y = height - 2*cm
            else:
                for rec in crosses[:12]:
                    c.drawString(x0+10, y, f"- {rec.get('month','')}: ratio={rec.get('ratio',0):.2f} → {rec.get('note','')}")
                    y -= lh
                    if y < 2*cm: c.showPage(); y = height - 2*cm

# ========== Next Actions page helper ==========
try:
    from .pdf_summary_additions import draw_next_actions_page  # จาก Exec Pack
except Exception:
    try:
        from pdf_summary_additions import draw_next_actions_page
    except Exception:
        # ===== Fallback: วาดหน้า Next Actions ภายในไฟล์นี้ =====
        def _wrap_text_inner(text, width):
            words = text.split()
            line, n = [], 0
            for w in words:
                n += len(w) + 1
                line.append(w)
                if n >= width:
                    yield " ".join(line)
                    line, n = [], 0
            if line:
                yield " ".join(line)
        def draw_next_actions_page(c: "canvas.Canvas", actions_result: dict):
            width, height = A4
            x0, y = 2 * cm, height - 2 * cm
            line_h = 14
            c.setFont("Helvetica-Bold", 16); c.drawString(x0, y, "Next Actions"); y -= 22
            c.setFont("Helvetica", 11)
            for idx, act in enumerate(actions_result.get("next_actions", []), start=1):
                title = act.get("title", ""); rationale = act.get("rationale", ""); how = act.get("how_to", [])
                c.setFont("Helvetica-Bold", 12); c.drawString(x0, y, f"{idx}. {title}"); y -= line_h
                c.setFont("Helvetica", 11)
                for chunk in _wrap_text_inner(f"Why: {rationale}", 100):
                    c.drawString(x0, y, chunk); y -= line_h
                    if y < 2 * cm: c.showPage(); y = height - 2 * cm
                for step in how:
                    for chunk in _wrap_text_inner(f"- {step}", 100):
                        c.drawString(x0 + 10, y, chunk); y -= line_h
                        if y < 2 * cm: c.showPage(); y = height - 2 * cm
                y -= 6
                if y < 2 * cm: c.showPage(); y = height - 2 * cm


def _ensure_calc(df):
    """
    รับ DataFrame แล้วให้แน่ใจว่ามีคอลัมน์สำหรับคำนวณ:
    - FX Adjusted Actual
    - Variance
    """
    data = df.copy()
    if "FX Adjusted Actual" not in data.columns:
        if "Actual" in data.columns:
            data["FX Adjusted Actual"] = data["Actual"]
        else:
            data["FX Adjusted Actual"] = 0
    if "Variance" not in data.columns:
        planned = data["Planned"] if "Planned" in data.columns else 0
        data["Variance"] = data["FX Adjusted Actual"] - planned
    return data


# ---------- Executive Summary (หน้าแรก) ----------
def _kpi_box(c, x, y, w, h, title, value, subtitle=None):
    """วาดกล่อง KPI แบบเรียบหรู"""
    c.setStrokeColor(colors.HexColor("#E0E0E0"))
    c.setFillColor(colors.white)
    c.roundRect(x, y - h, w, h, 8, stroke=1, fill=1)

    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#7A7A7A"))
    c.drawString(x + 10, y - 22, title)

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x + 10, y - 48, value)

    if subtitle:
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.HexColor("#7A7A7A"))
        c.drawString(x + 10, y - 66, subtitle)
    c.setFillColor(colors.black)


def _mean_or_none(series):
    try:
        return float(series.mean())
    except Exception:
        return None


def draw_executive_summary_page(c: "canvas.Canvas", df, actions_result=None):
    """หน้าแรก: KPI + ค่าเฉลี่ย % + Teaser Next Actions"""
    width, height = A4
    margin = 2 * cm
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, height - margin, "Executive Summary")

    c.setFont("Helvetica", 11)
    c.setFillColor(colors.HexColor("#555555"))
    c.drawString(margin, height - margin - 18, "Overview of key financial KPIs and immediate recommendations")
    c.setFillColor(colors.black)

    # KPIs
    total_plan = float(df.get("Planned", 0).sum()) if "Planned" in df.columns else 0.0
    total_actual_fx = float(df.get("FX Adjusted Actual", 0).sum()) if "FX Adjusted Actual" in df.columns else 0.0
    total_var = total_actual_fx - total_plan
    var_pct = (total_var / total_plan) if total_plan else 0.0

    gap = 0.6 * cm
    box_w = (width - margin * 2 - gap * 3) / 4
    box_h = 3.2 * cm
    top_y = height - margin - 30

    _kpi_box(c, margin + (box_w + gap) * 0, top_y, box_w, box_h, "Total Planned",          format_number(total_plan, "number"))
    _kpi_box(c, margin + (box_w + gap) * 1, top_y, box_w, box_h, "Total FX-Adjusted Actual", format_number(total_actual_fx, "number"))
    _kpi_box(c, margin + (box_w + gap) * 2, top_y, box_w, box_h, "Variance",               format_number(total_var, "number"), subtitle="Actual FX - Planned")
    _kpi_box(c, margin + (box_w + gap) * 3, top_y, box_w, box_h, "Variance % of Plan",     format_number(var_pct, "percent"))

    # Percent KPIs (avg)
    y2 = top_y - box_h - 20
    avail = [col for col in ["Margin", "Growth", "Utilization"] if col in df.columns]
    if avail:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y2, "Operating Ratios (avg)")
        y2 -= 14
        x = margin
        for col in avail:
            val = _mean_or_none(df[col])
            label = f"{col}: {format_number(val or 0, 'percent')}"
            c.setFont("Helvetica", 11)
            c.drawString(x, y2, label)
            x += 6.5 * cm

    # Teaser: Top Next Actions
    if actions_result and actions_result.get("next_actions"):
        y3 = y2 - 22
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y3, "Top Next Actions")
        y3 -= 14
        c.setFont("Helvetica", 11)
        for i, act in enumerate(actions_result["next_actions"][:3], start=1):
            title = act.get("title", "")
            c.drawString(margin, y3, f"{i}. {title}")
            y3 -= 14

    c.setStrokeColor(colors.HexColor("#EEEEEE"))
    c.line(margin, 2*cm, width - margin, 2*cm)
    c.setStrokeColor(colors.black)


def _wrap_text(text, width):
    words = text.split()
    line = []
    n = 0
    for w in words:
        n += len(w) + 1
        line.append(w)
        if n >= width:
            yield " ".join(line)
            line = []
            n = 0
    if line:
        yield " ".join(line)


def generate_pdf_with_chart(df, style_map=None, include_percent=True, add_next_actions=True, add_scenarios_alerts=True):
    """
    Generate PDF report:
      1) Executive Summary (KPI page)
      2) Main chart + grouped summary
      3) Next Actions (optional)
      4) Scenarios & Alerts (optional)
    """
    if style_map is None:
        style_map = {
            "Planned": "number",
            "FX Adjusted Actual": "number",
            "Variance": "number",
        }
        for col in PERCENT_COLUMNS:
            style_map[col] = "percent"

    # ให้แน่ใจว่ามีคอลัมน์ที่ใช้ในกราฟ/สรุป
    df = _ensure_calc(df)

    # เตรียม Next Actions สำหรับ Executive Summary teaser
    try:
        actions_result = suggest_as_dict(df)
    except Exception:
        actions_result = None

    # ====== สร้าง PDF ======
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4

    # ---------- Page 1: Executive Summary ----------
    draw_executive_summary_page(c, df, actions_result=actions_result)
    c.showPage()

    # ===== สรุปราย Cost Center (หรือทั้งก้อนถ้าไม่มีคอลัมน์) =====
    group_key = "Cost Center" if "Cost Center" in df.columns else None
    if group_key:
        grouped = df.groupby(group_key, as_index=False).agg({
            "Planned": "sum",
            "FX Adjusted Actual": "sum",
            "Variance": "sum"
        })
    else:
        grouped = df[["Planned", "FX Adjusted Actual", "Variance"]].sum(numeric_only=True).to_frame().T
        grouped.insert(0, "Cost Center", ["Total"])

    # เฉลี่ย percent columns ต่อ group
    if include_percent:
        percent_avgs = {}
        for col in PERCENT_COLUMNS:
            if col in df.columns:
                if group_key:
                    avg_col = df.groupby(group_key, as_index=False)[col].mean()
                else:
                    avg_col = df[[col]].mean(numeric_only=True).to_frame().T
                    avg_col.insert(0, "Cost Center", "Total")
                avg_col = avg_col.rename(columns={col: f"__avg__{col}"})
                percent_avgs[col] = avg_col

        for col, avgdf in percent_avgs.items():
            grouped = grouped.merge(avgdf, on="Cost Center", how="left")

    # ===== วาดกราฟ (Planned vs Actual by Cost Center) =====
    fig, ax = plt.subplots(figsize=(8, 4))
    bar_width = 0.35
    index = range(len(grouped))
    ax.bar(list(index), grouped["Planned"], bar_width, label="Planned")
    ax.bar([i + bar_width for i in index], grouped["FX Adjusted Actual"], bar_width, label="Actual")
    ax.set_xticks([i + bar_width / 2 for i in index])
    ax.set_xticklabels(grouped["Cost Center"], rotation=0)
    ax.set_ylabel("Cost (in units)")
    ax.set_title("Planned vs Actual by Cost Center")
    ax.legend()
    plt.tight_layout()

    chart_buffer = BytesIO()
    plt.savefig(chart_buffer, format="PNG")
    plt.close(fig)
    chart_buffer.seek(0)
    chart_bytes = chart_buffer.getvalue()

    # ---------- Page 2: Main chart + summary ----------
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, height - 50, "📊 Budget Summary Report")

    c.setFont("Helvetica", 12)
    c.drawString(60, height - 80, f"Total Records: {len(df)}")

    img_reader = ImageReader(BytesIO(chart_bytes))
    c.drawImage(img_reader, 60, height - 420, width=470, height=200, preserveAspectRatio=True, mask='auto')

    summary_y = height - 460
    line_height = 18
    for i, row in grouped.iterrows():
        text = (
            f"{row['Cost Center']}: "
            f"Planned={format_number(row['Planned'], style_map.get('Planned', 'number'))}, "
            f"Actual={format_number(row['FX Adjusted Actual'], style_map.get('FX Adjusted Actual', 'number'))}, "
            f"Var={format_number(row['Variance'], style_map.get('Variance', 'number'))}"
        )

        if include_percent:
            for col in PERCENT_COLUMNS:
                avg_key = f"__avg__{col}"
                if avg_key in grouped.columns:
                    text += f", {col}={format_number(row.get(avg_key, 0), style_map.get(col, 'percent'))}"

        y = summary_y - i * line_height
        if y < 60:
            c.showPage()
            c.setFont("Helvetica", 12)
            summary_y = height - 60
            y = summary_y
        c.drawString(60, y, text)

    # ---------- Page 3: Next Actions ----------
    if add_next_actions:
        c.showPage()
        try:
            actions = actions_result if actions_result else suggest_as_dict(df)
        except Exception:
            actions = {"next_actions": []}
        draw_next_actions_page(c, actions)

    # ---------- Page 4: Scenarios & Alerts ----------
    if add_scenarios_alerts:
        try:
            sc = compute_scenarios(df)          # ใช้ df หลัง ensure_calc
            al = scan_alerts(df, pct_threshold=0.08)
        except Exception:
            sc, al = {"summary": {}, "scenarios": []}, {"series": [], "crossings": [], "note": "Compute failed."}
        c.showPage()
        draw_scenarios_alerts_page(c, sc, al)

    # ปิดไฟล์
    c.showPage()
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer


def generate_pdf_default(df):
    """Helper → default: executive summary + main chart + next actions + scenarios/alerts"""
    return generate_pdf_with_chart(df, include_percent=True, add_next_actions=True, add_scenarios_alerts=True)
