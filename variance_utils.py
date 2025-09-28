import pandas as pd
from io import BytesIO

REQUIRED_COLUMNS = {"Version", "Scenario", "Cost Center", "Planned", "Actual"}
OPTIONAL_COLUMNS = {
    "FX Rate", "Approval Status", "Expense Type", "Commentary",
    "Role", "Threshold Alert", "Owner", "Line ID"
}

def validate_columns(df: pd.DataFrame):
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

def apply_fx_adjustment(df: pd.DataFrame) -> pd.DataFrame:
    if "FX Rate" in df.columns:
        df["FX Adjusted Actual"] = df["Actual"] * df["FX Rate"]
    else:
        df["FX Adjusted Actual"] = df["Actual"]
    return df

def compute_variance(df: pd.DataFrame) -> pd.DataFrame:
    df["Variance"] = df["FX Adjusted Actual"] - df["Planned"]
    return df

def log_ignored_columns(df: pd.DataFrame, logger=None):
    for col in OPTIONAL_COLUMNS:
        if col in df.columns:
            msg = f"Ignoring column '{col}' (not used in calculation)"
            if logger:
                logger.info(msg)
            else:
                print(msg)

def summarize_by_group(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby(["Version", "Scenario", "Cost Center"]).agg({
        "Planned": "sum",
        "FX Adjusted Actual": "sum",
        "Variance": "sum"
    }).reset_index()
    return grouped

def generate_excel_report(df: pd.DataFrame) -> BytesIO:
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    return buffer
