
"""
Next-action recommender for Budget Plus

Pure-Python, no external API calls. Uses simple rules on the uploaded DataFrame:
- Variance magnitude and direction
- FX contribution if "FX Rate" present
- Percent columns (Margin, Growth, Utilization) if present
- Category/Department drilldown suggestions
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

DEFAULT_THRESHOLDS = {
    "variance_warn_pct_of_plan": 0.10,   # variance > 10% of plan
    "fx_contrib_warn_pct": 0.30,         # FX explains >30% of variance
    "margin_warn": 0.20,                 # margin < 20%
    "growth_warn": 0.00,                 # growth <= 0
    "util_warn": 0.65,                   # utilization < 65%
    "top_n": 5
}

@dataclass
class NextAction:
    title: str
    rationale: str
    how_to: List[str]
    expected_outcome: Optional[str] = None
    tags: List[str] = field(default_factory=list)

@dataclass
class AnalysisSuggestion:
    summary: Dict[str, Any]
    next_actions: List[NextAction]
    drilldowns: Dict[str, List[str]]

def _fx_contribution_row(row: pd.Series) -> float:
    """
    Returns the portion of variance explained by FX for a row.
    If FX Rate column exists, FX Adjusted Actual - Actual reflects FX effect on actuals.
    """
    if "FX Rate" not in row.index:
        return 0.0
    actual = float(row.get("Actual", 0) or 0)
    fx_adj = float(row.get("FX Adjusted Actual", actual) or actual)
    planned = float(row.get("Planned", 0) or 0)
    # Total variance (fx_adj - planned)
    total_var = fx_adj - planned
    # FX-only delta relative to raw actuals
    fx_only = fx_adj - actual
    if total_var == 0:
        return 0.0
    return float(fx_only) / float(total_var)

def _safe_pct(num: float, den: float) -> float:
    if den == 0:
        return 0.0
    return float(num) / float(den)

def recommend_next_actions(df: pd.DataFrame, thresholds: Dict[str, float] = None) -> AnalysisSuggestion:
    th = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    data = df.copy()

    # Ensure calculation columns exist
    if "FX Adjusted Actual" not in data.columns:
        data["FX Adjusted Actual"] = data.get("Actual", 0)

    if "Variance" not in data.columns:
        data["Variance"] = data["FX Adjusted Actual"] - data.get("Planned", 0)

    # Summary metrics
    total_plan = float(data.get("Planned", pd.Series([0])).sum())
    total_actual_fx = float(data.get("FX Adjusted Actual", pd.Series([0])).sum())
    total_var = total_actual_fx - total_plan

    # Percent signals (if present)
    margin = float(data.get("Margin", pd.Series([None])).mean()) if "Margin" in data.columns else None
    growth = float(data.get("Growth", pd.Series([None])).mean()) if "Growth" in data.columns else None
    util = float(data.get("Utilization", pd.Series([None])).mean()) if "Utilization" in data.columns else None

    summary = {
        "total_planned": total_plan,
        "total_fx_adjusted_actual": total_actual_fx,
        "total_variance": total_var,
        "variance_pct_of_plan": _safe_pct(total_var, total_plan),
        "avg_margin": margin,
        "avg_growth": growth,
        "avg_utilization": util,
    }

    actions: List[NextAction] = []

    # Rule 1: Big unfavorable variance
    if total_plan != 0 and abs(total_var) / abs(total_plan) >= th["variance_warn_pct_of_plan"]:
        direction = "unfavorable" if total_var > 0 else "favorable"
        actions.append(NextAction(
            title=f"Drill down top {th['top_n']} variance drivers by Category and Department",
            rationale=f"Total variance is {direction} at {summary['variance_pct_of_plan']:.1%} of plan.",
            how_to=[
                "Group by Category, Department (and Month if available); sum Planned, Actual, FX Adjusted Actual, Variance.",
                "Rank by absolute Variance; focus on top drivers.",
                "For each driver, compare last 3 months trend vs baseline."
            ],
            expected_outcome="You will isolate 3–5 root drivers explaining ~80% of the gap.",
            tags=["variance", "driver-analysis"]
        ))

    # Rule 2: FX explains a large fraction of variance
    if "FX Rate" in data.columns:
        data["_fx_contrib"] = data.apply(_fx_contribution_row, axis=1)
        fx_weighted = float((data["_fx_contrib"] * data["Variance"].abs()).sum())
        var_weight = float((data["Variance"].abs()).sum()) or 1.0
        fx_contrib_pct = fx_weighted / var_weight
        if fx_contrib_pct >= th["fx_contrib_warn_pct"]:
            actions.append(NextAction(
                title="Run FX impact decomposition and simulate hedging scenarios",
                rationale=f"FX explains ~{fx_contrib_pct:.0%} of variance across drivers.",
                how_to=[
                    "For each Category, compute variance with FX=1.0 (neutral) vs actual FX.",
                    "Quantify the portion of gap due to FX vs operational factors.",
                    "Simulate ±5% FX moves to estimate sensitivity and recommend hedging size."
                ],
                expected_outcome="Quantified FX-attributable gap and hedging playbook.",
                tags=["fx", "hedging", "sensitivity"]
            ))

    # Rule 3: Low margin
    if margin is not None and margin < th["margin_warn"]:
        actions.append(NextAction(
            title="Margin rescue: decompose COGS vs SG&A pressure",
            rationale=f"Average margin {margin:.1%} is below the {th['margin_warn']:.0%} threshold.",
            how_to=[
                "Benchmark Margin by Category and Customer segment.",
                "Split variance into Price, Mix, Volume, and Cost effects if inputs available.",
                "Flag products with negative unit economics or discount leakage."
            ],
            expected_outcome="Set of actions to restore margin by 2–5 pp.",
            tags=["margin", "price", "cost"]
        ))

    # Rule 4: Negative growth
    if growth is not None and growth <= th["growth_warn"]:
        actions.append(NextAction(
            title="Sales pipeline vs actual conversion analysis",
            rationale=f"Average growth {growth:.1%} is at or below zero.",
            how_to=[
                "Compare forecast vs actual by month; compute forecast bias.",
                "Identify regions/products with steepest decline; correlate with FX and pricing changes.",
                "Propose recovery actions (promo, pricing, channel mix)."
            ],
            expected_outcome="Targeted recovery plan for next 1–2 quarters.",
            tags=["growth", "sales", "forecast-bias"]
        ))

    # Rule 5: Low utilization
    if util is not None and util < th["util_warn"]:
        actions.append(NextAction(
            title="Capacity utilization & cost absorption study",
            rationale=f"Average utilization {util:.1%} is below {th['util_warn']:.0%}.",
            how_to=[
                "Analyze fixed vs variable cost absorption by line/site.",
                "Simulate load increases to see margin recapture potential.",
                "Recommend temporary cost containment or load shift."
            ],
            expected_outcome="Actions to improve utilization and margin absorption.",
            tags=["utilization", "ops", "cost-absorption"]
        ))

    # Always propose baseline checks
    actions.append(NextAction(
        title="Early-warning trend scan",
        rationale="Proactive detection prevents month-end surprises.",
        how_to=[
            "Compute rolling 3-month trend for Planned vs Actual by driver.",
            "Flag crossings where Actual consistently exceeds Plan by >8%.",
            "Add alerts for sudden deltas vs prior month."
        ],
        expected_outcome="Lightweight alert feed for finance + ops.",
        tags=["early-warning", "trend", "alerts"]
    ))

    # Drilldown keys if present
    drilldowns: Dict[str, List[str]] = {}
    for key in ["Category", "Department", "Region", "Product", "Customer"]:
        if key in data.columns:
            top = (data.groupby(key)["Variance"].sum().abs().sort_values(ascending=False).head(th["top_n"]).index.tolist())
            drilldowns[key] = top

    return AnalysisSuggestion(
        summary=summary,
        next_actions=actions,
        drilldowns=drilldowns
    )

def suggest_as_dict(df: pd.DataFrame, thresholds: Dict[str, float] = None) -> Dict[str, Any]:
    s = recommend_next_actions(df, thresholds)
    return {
        "summary": s.summary,
        "next_actions": [
            {
                "title": a.title,
                "rationale": a.rationale,
                "how_to": a.how_to,
                "expected_outcome": a.expected_outcome,
                "tags": a.tags,
            } for a in s.next_actions
        ],
        "drilldowns": s.drilldowns
    }
