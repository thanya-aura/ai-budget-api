def forecast_from_drivers(df):
    """
    Generate driver-based forecasts.

    If a 'Driver' column is found, the function multiplies the driver by a fixed coefficient
    to estimate a budget forecast. Supports headcount-based or sales-linked forecasting.

    Parameters:
    - df (pd.DataFrame): Must contain 'Driver' and optionally 'Cost Type'.

    Returns:
    - pd.DataFrame: Modified DataFrame with new 'Driver Forecast' column.
    """
    try:
        if "Driver" not in df.columns:
            print("⚠️ Skipping driver-based forecasting — 'Driver' column not found.")
            return df

        # Default coefficient (could be made dynamic or learned from model)
        default_coefficient = 10000

        # Optional logic per cost type
        if "Cost Type" in df.columns:
            def dynamic_forecast(row):
                if row["Cost Type"].lower() == "salary":
                    return row["Driver"] * 12000
                elif row["Cost Type"].lower() == "sales":
                    return row["Driver"] * 15000
                else:
                    return row["Driver"] * default_coefficient
            df["Driver Forecast"] = df.apply(dynamic_forecast, axis=1)
        else:
            df["Driver Forecast"] = df["Driver"] * default_coefficient

        return df

    except Exception as e:
        print(f"⚠️ Error in driver forecasting: {e}")
        return df
