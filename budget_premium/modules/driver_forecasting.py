def forecast_from_drivers(df):
    if "Driver" in df.columns:
        df["Driver Forecast"] = df["Driver"] * 10000
    return df