
from fpdf import FPDF
from io import BytesIO
import matplotlib.pyplot as plt
import pandas as pd
from .number_format import format_currency

class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0,10,"Executive Budget Dashboard", ln=True, align="C")
        self.ln(2)
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial","I",8)
        self.cell(0,10,f"Page {self.page_no()}", align="C")

def generate_pdf_dashboard(df: pd.DataFrame, scale: str="raw", decimals:int=2) -> BytesIO:
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    # KPIs
    kpis = {
        "Total Planned": df["Planned"].sum() if "Planned" in df.columns else None,
        "Total Actual": df["Actual"].sum() if "Actual" in df.columns else None,
        "Total Adjusted": df["Adjusted Actual"].sum() if "Adjusted Actual" in df.columns else None,
        "Total Variance": df["Variance"].sum() if "Variance" in df.columns else None,
    }
    pdf.set_font("Arial","",11)
    for k,v in kpis.items():
        if v is not None:
            pdf.cell(0,8, f"{k}: {format_currency(v, scale=scale, decimals=decimals)}", ln=True)
    pdf.ln(2)
    # Top variances table
    if "Variance" in df.columns:
        top = df.reindex(df["Variance"].abs().sort_values(ascending=False).index)[:10]
        pdf.set_font("Arial","B",11); pdf.cell(0,8,"Top Variances", ln=True)
        pdf.set_font("Arial","",10)
        for _,r in top.iterrows():
            label = r.get("Cost Center", r.get("Project","Item"))
            pdf.cell(0,6, f"- {label}: {format_currency(r['Variance'], scale=scale, decimals=decimals)}", ln=True)
        pdf.ln(2)
    # Chart
    if {"Cost Center","Planned","Adjusted Actual"}.issubset(df.columns):
        chart = BytesIO()
        df.groupby("Cost Center")[["Planned","Adjusted Actual"]].sum().plot(kind="bar")
        plt.tight_layout()
        plt.savefig(chart, format="png")
        plt.close()
        chart.seek(0)
        y = pdf.get_y()
        pdf.image(chart, x=10, y=y, w=190)
    output = BytesIO()
    pdf.output(output)
    output.seek(0)
    return output
