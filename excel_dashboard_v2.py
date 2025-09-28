
"""
excel_dashboard_v2.py
Generate an Executive Dashboard Excel with:
- Dynamic dimension for variance chart (Category/Department/Region/Product/Customer/Cost Center)
- Scenarios sheet (±5% for FX/Price/Volume when columns available)
- Alerts sheet (rolling 3M trend crossing > 8%, requires Month column)
"""

from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np

from .scenarios_alerts import compute_scenarios, scan_alerts

DEFAULT_DIM_PRIORITY = ["Category", "Department", "Region", "Product", "Customer", "Cost Center"]

def _ensure_calc(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    if "FX Adjusted Actual" not in data.columns:
        data["FX Adjusted Actual"] = data.get("Actual", 0)
    if "Variance" not in data.columns:
        data["Variance"] = data["FX Adjusted Actual"] - data.get("Planned", 0)
    return data

def _pick_dim(data: pd.DataFrame, priority: Optional[List[str]]) -> Optional[str]:
    pr = priority or DEFAULT_DIM_PRIORITY
    for d in pr:
        if d in data.columns:
            return d
    return None

def generate_excel_dashboard_v2(
    df: pd.DataFrame,
    outfile: str,
    next_actions: Optional[Dict[str, Any]] = None,
    dim_priority: Optional[List[str]] = None,
    top_n: int = 10
) -> str:
    data = _ensure_calc(df)
    dim = _pick_dim(data, dim_priority)

    total_plan = float(data["Planned"].sum())
    total_actual_fx = float(data["FX Adjusted Actual"].sum())
    total_var = total_actual_fx - total_plan
    var_pct = (total_var / total_plan) if total_plan else 0.0

    # Group by chosen dim if available
    by_dim = None
    if dim:
        by_dim = (data.groupby(dim)[["Planned", "FX Adjusted Actual", "Variance"]]
                  .sum()
                  .sort_values("Variance", ascending=False))

    with pd.ExcelWriter(outfile, engine="xlsxwriter") as writer:
        wb = writer.book

        # Formats
        fmt_money = wb.add_format({"num_format": "#,##0", "align": "right"})
        fmt_pct = wb.add_format({"num_format": "0.0%", "align": "right"})
        fmt_kpi = wb.add_format({"bold": True, "font_size": 14})
        fmt_title = wb.add_format({"bold": True, "font_size": 16})
        fmt_hdr = wb.add_format({"bold": True, "bg_color": "#EEEEEE"})
        fmt_normal = wb.add_format({"text_wrap": True})

        # --- Executive Dashboard sheet
        sh = wb.add_worksheet("Executive Dashboard")
        sh.write(0, 0, "Executive Finance Dashboard", fmt_title)
        sh.write(1, 0, "Summary KPIs", fmt_kpi)
        sh.write(2, 0, "Total Planned"); sh.write(2, 1, total_plan, fmt_money)
        sh.write(3, 0, "Total FX-Adjusted Actual"); sh.write(3, 1, total_actual_fx, fmt_money)
        sh.write(4, 0, "Total Variance"); sh.write(4, 1, total_var, fmt_money)
        sh.write(5, 0, "Variance % of Plan"); sh.write(5, 1, var_pct, fmt_pct)

        # Plan vs Actual mini table for chart
        pv_row = 8
        sh.write(pv_row, 0, "Metric", fmt_hdr)
        sh.write(pv_row, 1, "Value", fmt_hdr)
        sh.write(pv_row+1, 0, "Planned"); sh.write(pv_row+1, 1, total_plan)
        sh.write(pv_row+2, 0, "FX Adjusted Actual"); sh.write(pv_row+2, 1, total_actual_fx)

        chart1 = wb.add_chart({"type": "column"})
        chart1.add_series({
            "name": ["Executive Dashboard", pv_row+1, 0],
            "categories": ["Executive Dashboard", pv_row+1, 0, pv_row+2, 0],
            "values": ["Executive Dashboard", pv_row+1, 1, pv_row+2, 1],
            "data_labels": {"value": True},
        })
        chart1.set_title({"name": "Plan vs FX-Adjusted Actual"})
        chart1.set_legend({"none": True})
        sh.insert_chart(1, 4, chart1, {"x_scale": 1.2, "y_scale": 1.2})

        # Variance by chosen dimension
        if by_dim is not None and len(by_dim) > 0:
            top = by_dim.head(top_n).reset_index()
            start_row = pv_row
            start_col = 4
            sh.write(start_row, start_col, dim, fmt_hdr)
            sh.write(start_row, start_col+1, "Variance", fmt_hdr)
            for i, row in top.iterrows():
                sh.write(start_row+1+i, start_col, str(row[dim]))
                sh.write(start_row+1+i, start_col+1, float(row["Variance"]), fmt_money)

            chart2 = wb.add_chart({"type": "bar"})
            chart2.add_series({
                "name": f"Variance by {dim} (Top {top_n})",
                "categories": ["Executive Dashboard", start_row+1, start_col, start_row+len(top), start_col],
                "values": ["Executive Dashboard", start_row+1, start_col+1, start_row+len(top), start_col+1],
                "data_labels": {"value": True},
            })
            chart2.set_title({"name": f"Variance by {dim} (Top {top_n})"})
            chart2.set_legend({"none": True})
            sh.insert_chart(16, 4, chart2, {"x_scale": 1.6, "y_scale": 1.6})

        # Next Actions (if provided)
        row = 20
        if next_actions and "next_actions" in next_actions:
            sh.write(row, 0, "Next Actions", fmt_kpi)
            row += 1
            for i, act in enumerate(next_actions["next_actions"][:6], start=1):
                sh.write(row, 0, f"{i}. {act.get('title','')}")
                sh.write(row+1, 0, f"Why: {act.get('rationale','')}", fmt_normal)
                how = act.get("how_to", [])
                for j, step in enumerate(how[:5], start=1):
                    sh.write(row+1+j, 0, f"- {step}", fmt_normal)
                row += 3 + min(len(how), 5)

        # Details sheet
        data.to_excel(writer, index=False, sheet_name="Details")
        ws_details = writer.sheets["Details"]
        for idx, col in enumerate(data.columns):
            ws_details.set_column(idx, idx, 18)

        # Drivers sheet (top abs variance)
        drv = (data.assign(abs_var=lambda d: d["Variance"].abs())
               .sort_values("abs_var", ascending=False)
               .head(max(top_n, 10)))
        drv.drop(columns=["abs_var"], inplace=True)
        drv.to_excel(writer, index=False, sheet_name="Drivers")
        ws_drv = writer.sheets["Drivers"]
        for idx, col in enumerate(drv.columns):
            ws_drv.set_column(idx, idx, 18)

        # Scenarios sheet
        sc = compute_scenarios(data)
        sc_df = pd.DataFrame(sc["scenarios"])
        sc_df.to_excel(writer, index=False, sheet_name="Scenarios")
        ws_sc = writer.sheets["Scenarios"]
        for idx, col in enumerate(sc_df.columns):
            ws_sc.set_column(idx, idx, 22)
        # header values
        ws_sc.write(0, len(sc_df.columns)+1, "Base Planned")
        ws_sc.write(1, len(sc_df.columns)+1, sc["summary"]["base_planned"])
        ws_sc.write(0, len(sc_df.columns)+2, "Base Variance")
        ws_sc.write(1, len(sc_df.columns)+2, sc["summary"]["base_variance"])

        # Alerts sheet
        al = scan_alerts(data, pct_threshold=0.08)
        # time series
        ser_cols = ["Month", "Planned", "FX Adjusted Actual", "ratio", "rolling3m"]
        ser_df = pd.DataFrame(al.get("series", []))
        if not ser_df.empty:
            ser_df.to_excel(writer, index=False, sheet_name="Alerts")
            ws_al = writer.sheets["Alerts"]
            for idx, col in enumerate(ser_df.columns):
                ws_al.set_column(idx, idx, 18)
            # crossings table appended below
            start = len(ser_df) + 3
            ws_al.write(start, 0, "Crossings (Rolling 3M > 8%)", fmt_kpi)
            cross = pd.DataFrame(al.get("crossings", []))
            if not cross.empty:
                for i, col in enumerate(["month", "ratio", "note"]):
                    ws_al.write(start+1, i, col, fmt_hdr)
                for r, rec in enumerate(al["crossings"], start=start+2):
                    ws_al.write(r, 0, rec.get("month",""))
                    ws_al.write(r, 1, rec.get("ratio", 0.0))
                    ws_al.write(r, 2, rec.get("note",""))
        else:
            # create Alerts sheet with note
            ws_al = wb.add_worksheet("Alerts")
            ws_al.write(0, 0, "No 'Month' column; Alerts skipped.", fmt_normal)

    return outfile
