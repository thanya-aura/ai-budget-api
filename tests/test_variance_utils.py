import pandas as pd
from io import BytesIO
from budget_plus.utils.variance_utils import (
    calculate_variance,
    summarize_variance,
    audit_variance,
    ai_suggest_variance,
)
from budget_plus.pdf_summary import generate_pdf_with_chart


def test_calculate_variance_numeric():
    df = pd.DataFrame({
        "Version": ["V1", "V1"],
        "Scenario": ["Base", "Base"],
        "Cost Center": ["CC1", "CC2"],
        "Planned": [1000, 2000],
        "Actual": [1100, 1900],
        "FX Rate": [1.0, 1.1]
    })

    df_out = calculate_variance(df.copy())
    assert "FX Adjusted Actual" in df_out.columns
    assert "Variance" in df_out.columns
    assert isinstance(df_out.loc[0, "Variance"], (int, float))
    assert df_out.loc[0, "Variance"] == 100  # 1100 - 1000
    assert round(df_out.loc[1, "Variance"], 2) == round(1900 * 1.1 - 2000, 2)


def test_summarize_variance_grouping():
    df = pd.DataFrame({
        "Version": ["V1", "V1", "V2"],
        "Scenario": ["Base", "Base", "Stress"],
        "Cost Center": ["CC1", "CC1", "CC2"],
        "Planned": [100, 200, 300],
        "Actual": [120, 210, 280],
    })

    df = calculate_variance(df)
    summary = summarize_variance(df)

    assert set(summary.columns) == {"Version", "Scenario", "Cost Center", "Planned", "Actual", "Variance"}
    assert summary[summary["Cost Center"] == "CC1"]["Planned"].iloc[0] == 300
    assert summary[summary["Cost Center"] == "CC1"]["Actual"].iloc[0] == 330


def test_audit_variance_placeholder():
    df = pd.DataFrame({"Planned": [100], "Actual": [120]})
    result = audit_variance(df)
    assert isinstance(result, dict)
    assert "status" in result


def test_ai_suggest_variance_placeholder():
    df = pd.DataFrame({"Planned": [100], "Actual": [120]})
    result = ai_suggest_variance(df)
    assert isinstance(result, dict)
    assert "suggestion" in result


def test_pdf_generation_with_k_and_m_style_map_and_percent():
    """
    ทดสอบ generate_pdf_with_chart() โดยต้องคำนวณ FX Adjusted Actual / Variance ก่อน
    แล้วส่ง style_map:
      - Planned → m
      - FX Adjusted Actual → k
      - Variance → number
      - Margin → percent
    """
    df = pd.DataFrame({
        "Cost Center": ["A", "B"],
        "Planned": [1_200_000, 2_500_000],
        "Actual": [600_000, 1_200_000],
        "FX Rate": [1.0, 1.0],
        "Margin": [0.1234, 0.2567],
        "Version": ["V1", "V1"],
        "Scenario": ["Base", "Base"],
    })

    # ✅ คำนวณก่อน เพื่อให้มีคอลัมน์ที่ PDF ต้องใช้
    df_calc = calculate_variance(df.copy())

    style_map = {
        "Planned": "m",
        "FX Adjusted Actual": "k",
        "Variance": "number",
        "Margin": "percent",
    }
    buffer = generate_pdf_with_chart(df_calc, style_map=style_map, include_percent=True)
    assert isinstance(buffer, BytesIO)
    assert len(buffer.getvalue()) > 1500
