# pdf_summary.py

# ใช้ backend ที่ไม่ต้องมีจอ (สำหรับ Render/Server)
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from PIL import Image

# --- รองรับทั้งรันแบบแพ็กเกจ และรันจากราก repo ---
try:
    # กรณีรันแบบแพ็กเกจ (uvicorn budget_plus.main:app)
    from .utils.number_format_utils import format_number
    from .config import PERCENT_COLUMNS
except ImportError:
    # กรณีรันแบบ root module (uvicorn main:app)
    from utils.number_format_utils import format_number
    from config import PERCENT_COLUMNS


def generate_pdf_with_chart(df, style_map=None, include_percent=True):
    """
    Generate PDF report with chart and formatted summary.
    - ค่า numeric จะคงเดิม ใช้คำนวณต่อได้
    - format เฉพาะตอน render เป็นข้อความใน PDF
    """
    if style_map is None:
        style_map = {
            "Planned": "number",
            "FX Adjusted Actual": "number",
            "Variance": "number",
        }
        for col in PERCENT_COLUMNS:
            style_map[col] = "percent"

    # ✅ สรุปค่า numeric ต่อ Cost Center
    grouped = df.groupby("Cost Center", as_index=False).agg({
        "Planned": "sum",
        "FX Adjusted Actual": "sum",
        "Variance": "sum"
    })

    # ✅ สรุป percent columns (ใช้ค่าเฉลี่ย) แล้ว merge เข้ากับ grouped
    if include_percent:
        percent_avgs = {}
        for col in PERCENT_COLUMNS:
            if col in df.columns:
                avg_col = (
                    df.groupby("Cost Center", as_index=False)[col]
                    .mean()
                    .rename(columns={col: f"__avg__{col}"})
                )
                percent_avgs[col] = avg_col

        for col, avgdf in percent_avgs.items():
            grouped = grouped.merge(avgdf, on="Cost Center", how="left")

    # --- วาดกราฟ ---
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

    # ใช้ข้อมูลภาพแบบ bytes ตรง ๆ กับ reportlab (หลีกเลี่ยงปัญหา ImageReader.format)
    # - ไม่ต้องเปิดด้วย PIL ก่อน
    # - ส่ง buffer ใหญ่เข้าไปได้เลย
    chart_bytes = chart_buffer.getvalue()

    # --- สร้าง PDF ---
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, height - 50, "📊 Budget Summary Report")

    c.setFont("Helvetica", 12)
    c.drawString(60, height - 80, f"Total Records: {len(df)}")

    # ใส่รูปด้วย ImageReader โดยใช้ bytes โดยตรง
    from reportlab.lib.utils import ImageReader
    img_reader = ImageReader(BytesIO(chart_bytes))
    c.drawImage(img_reader, 60, height - 420, width=470, height=200, preserveAspectRatio=True, mask='auto')

    # --- Summary text ---
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

        # ตัดขึ้นหน้าใหม่ถ้าพื้นที่ไม่พอ
        y = summary_y - i * line_height
        if y < 60:
            c.showPage()
            c.setFont("Helvetica", 12)
            summary_y = height - 60
            y = summary_y
        c.drawString(60, y, text)

    c.showPage()
    c.save()
    pdf_buffer.seek(0)

    return pdf_buffer


def generate_pdf_default(df):
    """Helper → default format (percent columns เฉลี่ยเป็นค่าแสดงผล)"""
    return generate_pdf_with_chart(df, include_percent=True)
