
import pandas as pd

def recommend_next_actions(df: pd.DataFrame) -> list[dict]:
    recs = []
    # Example heuristics on existing columns
    if "Variance" in df.columns:
        big = df["Variance"].abs().nlargest(3).index.tolist()
        if len(big):
            recs.append({"type":"deep-dive", "title":"Investigate top variance drivers",
                         "why":"Largest variance lines often hide controllable drivers",
                         "how":"Drill into Cost Center, Project, and FX impacts for rows: " + ", ".join(map(str,big))})
    if {"Planned","Actual"}.issubset(df.columns):
        over = df[df["Actual"]>df["Planned"]]
        if not over.empty:
            recs.append({"type":"control","title":"Tighten spend controls on overshooting items",
                         "why":"Actuals exceed plan","how":"Review approvals and accruals for top overspends"})
    if "FX Rate" in df.columns:
        recs.append({"type":"hedge","title":"Run FX sensitivity scenarios",
                     "why":"Volatile currency can distort actuals","how":"Apply +/-5%, +/-10% FX shocks to see exposure"})
    if "Driver" in df.columns:
        recs.append({"type":"forecast","title":"Update driver-based forecast",
                     "why":"Driver changes can refresh next-quarter outlook",
                     "how":"Use driver_forecasting to regenerate forecast and compare to plan"})
    # Generic always-on
    recs.append({"type":"executive","title":"Generate Executive Dashboard (PDF + Excel)",
                 "why":"Communicate insights quickly","how":"Export summary with variances, KPIs, and charts"})
    return recs
