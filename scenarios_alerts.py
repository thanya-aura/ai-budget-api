
"""
scenarios_alerts.py
Utilities to compute scenarios (±5% FX/Price/Volume) and scan alerts
(rolling 3M trend crossing > 8%) from a budget dataframe.
"""

from typing import Dict, Any, List
import pandas as pd
import numpy as np

def _ensure_calc(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    if "FX Adjusted Actual" not in data.columns:
        data["FX Adjusted Actual"] = data.get("Actual", 0)
    if "Variance" not in data.columns:
        data["Variance"] = data["FX Adjusted Actual"] - data.get("Planned", 0)
    return data

def compute_scenarios(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Returns {"summary": {...}, "scenarios": [{name,total_plan,total_actual_fx,total_variance,delta_vs_base}, ...]}
    Scenarios supported (graceful skip if columns missing):
      - FX +/-5% if "FX Rate" exists
      - Price +/-5% if "Price" and "Quantity" exist
      - Volume +/-5% if "Quantity" exists
    Base is totals of df (uses FX Adjusted Actual if present).
    """
    data = _ensure_calc(df)
    res = {"summary": {}, "scenarios": []}

    base_plan = float(data.get("Planned", 0).sum())
    base_actual_fx = float(data.get("FX Adjusted Actual", 0).sum())
    base_var = base_actual_fx - base_plan
    res["summary"] = {"base_planned": base_plan, "base_actual_fx": base_actual_fx, "base_variance": base_var}

    def add_scenario(name: str, actual_fx_series: pd.Series):
        total_actual_fx = float(actual_fx_series.sum())
        var = total_actual_fx - base_plan
        res["scenarios"].append({
            "name": name,
            "total_planned": base_plan,
            "total_actual_fx": total_actual_fx,
            "total_variance": var,
            "delta_vs_base": var - base_var
        })

    # FX scenarios
    if "FX Rate" in data.columns and "Actual" in data.columns:
        for pct in (+0.05, -0.05):
            fx = (data["FX Rate"] * (1.0 + pct))
            add_scenario(f"FX {int(pct*100)}%", data["Actual"] * fx)

    # Price scenarios
    if "Price" in data.columns and "Quantity" in data.columns:
        # Recompute actual from price*qty as a baseline if not wildly missing
        base_actual_from_pq = (data["Price"] * data["Quantity"])
        for pct in (+0.05, -0.05):
            add_scenario(f"Price {int(pct*100)}%", (data["Price"] * (1.0 + pct)) * data["Quantity"])

    # Volume scenarios
    if "Quantity" in data.columns and ("Price" in data.columns or "Actual" in data.columns):
        # If Price exists, use price*qty; else assume Actual scales with quantity proportionally
        if "Price" in data.columns:
            for pct in (+0.05, -0.05):
                add_scenario(f"Volume {int(pct*100)}%", data["Price"] * (data["Quantity"] * (1.0 + pct)))
        else:
            # scale FX Adjusted Actual by qty factor if base qty exists
            if "Quantity" in data.columns:
                q = data["Quantity"].astype(float).replace(0, np.nan)
                scale_up = (q * 1.05) / q
                scale_dn = (q * 0.95) / q
                add_scenario("Volume 5%", data["FX Adjusted Actual"] * scale_up.fillna(1.0))
                add_scenario("Volume -5%", data["FX Adjusted Actual"] * scale_dn.fillna(1.0))

    return res

def scan_alerts(df: pd.DataFrame, pct_threshold: float = 0.08) -> Dict[str, Any]:
    """
    Rolling 3M trend crossing > pct_threshold (default 8%).
    Requires a 'Month' column (datetime-like or string convertible).
    Returns { "series": DataFrame-like dict, "crossings": [ {month, ratio, note}, ...] }
    """
    out: Dict[str, Any] = {"series": [], "crossings": []}
    data = _ensure_calc(df)

    if "Month" not in data.columns:
        out["note"] = "No 'Month' column; Alerts skipped."
        return out

    s = data.copy()
    s["Month"] = pd.to_datetime(s["Month"], errors="coerce")
    s = s.dropna(subset=["Month"])

    by_m = s.groupby("Month")[["Planned", "FX Adjusted Actual"]].sum().sort_index()
    by_m["ratio"] = by_m["FX Adjusted Actual"] / by_m["Planned"].replace(0, pd.NA)
    by_m["ratio"] = by_m["ratio"].fillna(1.0)  # if plan==0, treat as neutral
    by_m["rolling3m"] = by_m["ratio"].rolling(window=3, min_periods=3).mean()

    # crossing: rolling3m >= 1 + threshold
    flagged = by_m[by_m["rolling3m"] >= (1.0 + pct_threshold)]
    for month, row in flagged.iterrows():
        out["crossings"].append({
            "month": str(month.date()),
            "ratio": float(row["rolling3m"]),
            "note": f"Rolling 3M Actual > Plan by {pct_threshold*100:.0f}%+"
        })

    out["series"] = by_m.reset_index().to_dict(orient="records")
    return out
