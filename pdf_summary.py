# pdf_summary.py

# ใช้ backend แบบ headless เพื่อเลี่ยงปัญหา GUI/เซิร์ฟเวอร์
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from io import BytesIO
from typing import Any

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
# PIL ไม่จำเป็นแล้วสำหรับส่วนรูปกราฟนี้ แต่จะคง import ไว้หากคุณใช้ที่อื่น
# from PIL import Image

from .utils.number_format_utils import format_number
from .config import PERCENT_COLUMNS


def _safe_get_row_val(row: pd.Series, key: str, default: Any = 0) -> Any:
    """ดึงค่าจากแถว (Series) อย่างปลอดภัย + แปลง NaN เป็น default"""
    try:
        val = row.get(key, default)
    except Exception:
        val = default
    try:
        if pd.isna(val):
            return default
    except Exception:
        pass
    return val


def generate_pdf_with_chart(
    df: pd.DataFrame,
    style_map: dict[str, str] | None = None,
    include_percent: bool = True
) -> BytesIO:
    """
    Generate PDF report with chart and formatted summary.
    - ค่า numeric คงเดิม ใช้คำนวณต่อได้
    - format เฉพาะตอน render เป็นข้อความใน PDF
    """
    if style_map is None:
        style_map = {
            "Planned": "number",
            "FX Adjusted Actual": "number",
            "Variance": "number",
        }
    if include_percent:
        for col in PERCENT_COLUMNS:
            style_map.setdefault(col, "percent")

    # ตรวจคอลัมน์จำเป็น
    if "Cost Center" not in df.columns:
        raise ValueError("DataFrame ต้องมีคอลัมน์ 'Cost Center'")

    for col in ["Planned", "FX Adjusted Actual", "Variance"]:
        if col not in df.columns:
            df[col] = 0

    # สรุปตัวเลขต่อ Cost Center
    grouped = df.groupby("Cost Center", as_index=False).agg({
        "Planned": "sum",
        "FX Adjusted Actual": "sum",
        "Variance": "sum"
    })

    # สรุปเปอร์เซ็นต์ (เฉลี่ย) และ merge
    if include_percent and PERCENT_COLUMNS:
        for col in PERCENT_COLUMNS:
            if col in df.columns:
                avgdf = (
                    df.groupby("Cost Center", as_index=False)[col]
                    .mean(numeric_only=True)
                    .rename(columns={col: f"__avg__{col}"})
                )
                grouped = grouped.merge(avgdf, on="Cost Center", how="left")

    # เผื่อกรณีไม่มีข้อมูล
    if grouped.empty:
        grouped = pd.DataFrame(
            {"Cost Center": ["(no data)"], "Planned": [0], "FX Adjusted Actual": [0], "Variance": [0]}
        )

    # ----- วาดกราฟ -----
    fig, ax = plt.subplots(figsize=(8, 4))
    bar_width = 0.35
    idx = list(range(len(grouped)))

    planned_vals = grouped["Planned"].fillna(0).tolist()
    actual_vals = grouped["FX Adjusted Actual"].fillna(0).tolist()

    ax.bar(idx, planned_vals, bar_width, label="Planned")
    ax.bar([i + bar_width for i in idx], actual_vals, bar_width, label="Actual")

    ax.set_xticks([i + bar_width / 2 for i in idx])
    ax.set_xticklabels(grouped["Cost Center"], rotation=20, ha="right")
    ax.set_ylabel("Cost (in units)")
    ax.set_title("Planned vs Actual by Cost Center")
    ax.legend()
    plt.tight_layout()

    chart_buffer = BytesIO()
    plt.savefig(chart_buffer, format="PNG", dpi=150)
    plt.close(fig)
    chart_buffer.seek(0)

    # ⬇️ ใช้ ImageReader กับ buffer โดยตรง
    img_reader = ImageReader(chart_buffer)

    # ----- สร้าง PDF -----
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, height - 50, "📊 Budget Summary Report")
    c.setFont("Helvetica", 12)
    c.drawString(60, height - 80, f"Total Records: {len(df)}")

    # ⬇️ เปลี่ยนมาใช้ drawImage (เสถียรกว่า drawInlineImage กับ ImageReader)
    c.drawImage(img_reader, 60, height - 420, width=470, height=200, mask='auto')

    # Summary (มีตัดหน้าใหม่อัตโนมัติ)
    c.setFont("Helvetica", 10)
    y = height - 460
    line_h = 18
    max_lines = int((y - 40) / line_h)
    lines = 0

    for _, row in grouped.iterrows():
        text = (
            f"{row['Cost Center']}: "
            f"Planned={format_number(_safe_get_row_val(row, 'Planned', 0), style_map.get('Planned', 'number'))}, "
            f"Actual={format_number(_safe_get_row_val(row, 'FX Adjusted Actual', 0), style_map.get('FX Adjusted Actual', 'number'))}, "
            f"Var={format_number(_safe_get_row_val(row, 'Variance', 0), style_map.get('Variance', 'number'))}"
        )

        if include_percent:
            for col in PERCENT_COLUMNS:
                avg_key = f"__avg__{col}"
                if avg_key in grouped.columns:
                    text += f", {col}={format_number(_safe_get_row_val(row, avg_key, 0), style_map.get(col, 'percent'))}"

        if lines >= max_lines:
            c.showPage()
            c.setFont("Helvetica-Bold", 16)
            c.drawString(60, height - 50, "📊 Budget Summary Report (cont.)")
            c.setFont("Helvetica", 10)
            y = height - 80
            lines = 0

        c.drawString(60, y, text)
        y -= line_h
        lines += 1

    c.showPage()
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer


def generate_pdf_default(df: pd.DataFrame) -> BytesIO:
    """Helper → default format (percent columns เฉลี่ยเป็นค่าแสดงผล)"""
    return generate_pdf_with_chart(df, include_percent=True)
