
import pandas as pd
from .number_format import format_currency, format_percent, apply_scale_series

def add_formatted_columns(df: pd.DataFrame, money_cols=None, pct_cols=None, scale="raw", decimals=2, pct_decimals=2):
    money_cols = money_cols or []
    pct_cols = pct_cols or []
    out = df.copy()
    # numeric scaling for compute columns
    for c in money_cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
            out[c] = out[c]  # keep numeric for downstream calc
            out[f"{c} (disp)"] = out[c].apply(lambda x: format_currency(x, scale=scale, decimals=decimals))
    for c in pct_cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
            out[f"{c} (disp)"] = out[c].apply(lambda x: format_percent(x, decimals=pct_decimals))
    return out
