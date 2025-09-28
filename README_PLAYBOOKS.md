
# Playbooks + /report-exec Integration Pack

This pack includes:
- `playbooks/` (12 YAML playbooks)
- `playbooks_loader.py` → load + select playbooks based on `summary` from `suggest_as_dict(df)`
- `excel_playbooks_append.py` → append a "Playbooks" sheet to the Executive Dashboard Excel
- `report_playbooks_pdf.py` → generate a separate Playbooks PDF
- `report_exec_routes.py` → FastAPI router exposing `POST /report-exec` that returns a ZIP bundle:
  - `Executive_Dashboard.xlsx`
  - `Budget_Executive_Report.pdf`
  - `Executive_Playbooks.pdf`
  - `manifest.json`

## How to integrate (quick)
1. Copy all files to your `budget_plus/` package (keep the `playbooks/` folder inside the same directory as `report_exec_routes.py`).
2. In `budget_plus/main.py` add:
   ```python
   from .report_exec_routes import router as report_exec_router
   app.include_router(report_exec_router)
   ```
3. Restart your app. Now you can POST an Excel file to `/report-exec` and receive a ZIP bundle.

## Notes
- You can add more YAML playbooks: drop new `.yaml` into `playbooks/`.
- The condition language is a simple Python expression evaluated against `summary`. Example:
  `summary.variance_pct_of_plan >= 0.1 and summary.total_planned > 0`
