from fpdf import FPDF
import matplotlib
matplotlib.use("Agg")   # ต้องมาก่อน pyplot
import matplotlib.pyplot as plt
from io import BytesIO
import pandas as pd
from PIL import Image


def generate_pdf_summary(df: pd.DataFrame) -> BytesIO:
    """
    Generate a professional PDF summary with variance alerts and a summary chart.

    Parameters:
    - df (pd.DataFrame): Input budget DataFrame (must contain 'Cost Center', 'Project', 'Planned', 'Adjusted Actual', 'Variance')

    Returns:
    - BytesIO: PDF file-like object for download or response
    """
    # Create PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(200, 10, "📊 Budget Summary Dashboard", ln=True, align="C")
    pdf.set_font("Arial", size=11)

    # Add alert section
    pdf.ln(10)
    alert_rows = df[df["Variance"].abs() > 2000]
    if alert_rows.empty:
        pdf.cell(200, 10, "✅ No variance alerts exceed the threshold of ±2,000", ln=True)
    else:
        pdf.set_text_color(220, 50, 50)  # red
        for _, row in alert_rows.iterrows():
            alert_text = f"⚠️ {row['Cost Center']} | {row['Project']} → Variance = {row['Variance']:.2f}"
            pdf.multi_cell(0, 8, alert_text)

    pdf.set_text_color(0, 0, 0)

    # Add bar chart
    chart_img = BytesIO()
    summary = df.groupby("Cost Center")[["Planned", "Adjusted Actual"]].sum()
    ax = summary.plot(kind="bar", figsize=(8, 4))
    ax.set_title("Planned vs Adjusted Actual by Cost Center")
    ax.set_ylabel("Amount")
    ax.set_xlabel("Cost Center")
    plt.tight_layout()
    plt.savefig(chart_img, format="png")
    plt.close()
    chart_img.seek(0)

    # Convert PNG chart to PIL Image for FPDF compatibility
    chart_pil = Image.open(chart_img).convert("RGB")
    temp_img = BytesIO()
    chart_pil.save(temp_img, format="PNG")
    temp_img.seek(0)

    # Save PIL image to temporary file for FPDF (FPDF requires filename or path-like object)
    img_path = "temp_chart.png"
    with open(img_path, "wb") as f:
        f.write(temp_img.read())

    # Embed image
    pdf.image(img_path, x=15, y=pdf.get_y() + 10, w=180)

    # Generate final output
    output = BytesIO()
    pdf.output(output)
    output.seek(0)

    return output
