from fpdf import FPDF
import matplotlib
matplotlib.use("Agg")   # ต้องมาก่อน pyplot
import matplotlib.pyplot as plt
from io import BytesIO

def generate_pdf_summary(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, "Budget Summary Dashboard", ln=True, align="C")
    for _, row in df[df["Variance"].abs() > 2000].iterrows():
        pdf.cell(200, 10, f"⚠️ Variance - {row['Cost Center']} | {row['Project']} = {row['Variance']:.2f}", ln=True)
    chart = BytesIO()
    df.groupby("Cost Center")[["Planned", "Adjusted Actual"]].sum().plot(kind="bar")
    plt.tight_layout()
    plt.savefig(chart, format="png")
    chart.seek(0)
    pdf.image(chart, x=10, y=pdf.get_y()+5, w=180)
    output = BytesIO()
    pdf.output(output)
    output.seek(0)
    return output