import pandas as pd

def calculate_variance(df: pd.DataFrame) -> pd.DataFrame:
    """
    เพิ่มคอลัมน์ FX Adjusted Actual และ Variance
    คืน DataFrame พร้อมค่าตัวเลข (numeric) ใช้ต่อในคำนวณได้
    """
    if "FX Rate" in df.columns:
        df["FX Adjusted Actual"] = df["Actual"] * df["FX Rate"]
    else:
        df["FX Adjusted Actual"] = df["Actual"]

    df["Variance"] = df["FX Adjusted Actual"] - df["Planned"]
    return df

def summarize_variance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group ตาม Version, Scenario, Cost Center
    คืนค่า numeric summary
    """
    summary = df.groupby(["Version", "Scenario", "Cost Center"], as_index=False).agg({
        "Planned": "sum",
        "Actual": "sum",
        "FX Adjusted Actual": "sum",
        "Variance": "sum"
    })
    return summary

def audit_variance(df: pd.DataFrame):
    """Placeholder สำหรับ Audit logic"""
    return {"status": "ok", "notes": "audit not implemented yet"}

def ai_suggest_variance(df: pd.DataFrame):
    """Placeholder สำหรับ AI Suggestion logic"""
    return {"status": "ok", "suggestion": "AI suggestions not implemented yet"}
