
# Dashboard v2 Pack — Dims + Scenarios + Alerts

Files:
- `scenarios_alerts.py` → compute_scenarios(df), scan_alerts(df)
- `excel_dashboard_v2.py` → generate_excel_dashboard_v2(..., dim_priority=[...])
- `pdf_enhancements_alerts.py` → draw_scenarios_alerts_page(canvas, scenarios, alerts)

## Excel Integration
In `budget_plus/main.py` (or your routes), replace previous Excel generator call:
```python
from .excel_dashboard_v2 import generate_excel_dashboard_v2
from .scenarios_alerts import compute_scenarios, scan_alerts
...
# inside endpoint:
scenarios = compute_scenarios(df_calc)
alerts = scan_alerts(df_calc, pct_threshold=0.08)
generate_excel_dashboard_v2(df_calc, outpath, next_actions=actions, dim_priority=["Category","Department","Region"])
```
This produces sheets: Executive Dashboard, Details, Drivers, **Scenarios**, **Alerts**.

## PDF Integration
In `budget_plus/pdf_summary.py` after Next Actions page:
```python
from .scenarios_alerts import compute_scenarios, scan_alerts
from .pdf_enhancements_alerts import draw_scenarios_alerts_page
...
sc = compute_scenarios(df)  # df after ensure/calc
al = scan_alerts(df, pct_threshold=0.08)
c.showPage()
draw_scenarios_alerts_page(c, sc, al)
```

## Dimension Storytelling
You can control the dimension used for the variance chart by passing `dim_priority=[...]`.
The function picks the **first available** column from that list among your data.
