def apply_scenarios(df):
    if "Scenario" in df.columns:
        df["Best Case"] = df["Planned"] * 0.95
        df["Worst Case"] = df["Planned"] * 1.10
    return df