import pandas as pd
import sys
import os

# Add project root to sys.path to find pdf_summary.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pdf_summary import generate_pdf_with_chart


def test_generate_pdf_creates_buffer():
    # Sample minimal DataFrame
    df = pd.DataFrame({
        "Cost Center": ["HR", "IT"],
        "Planned": [100000, 150000],
        "Actual": [95000, 160000],
        "FX Rate": [1.0, 1.0]
    })
    df["FX Adjusted Actual"] = df["Actual"] * df["FX Rate"]
    df["Variance"] = df["FX Adjusted Actual"] - df["Planned"]

    buffer = generate_pdf_with_chart(df)

    assert buffer is not None, "PDF buffer was not returned"
    assert isinstance(buffer.getvalue(), bytes), "PDF content is not in bytes format"
    assert len(buffer.getvalue()) > 1000, "PDF content size too small (may indicate failure)"
