def suggest_reallocation(row):
    """
    Provides AI-like suggestions for reallocation based on variance thresholds.

    Parameters:
    - row (pd.Series): A row of the DataFrame with at least a "Variance" field.

    Returns:
    - str: Suggestion string.
    """
    try:
        variance = row.get("Variance", 0)

        # High positive variance (under-utilized budget)
        if variance > 3000:
            return "💡 Consider reallocating from surplus departments"

        # High negative variance (overspend)
        elif variance < -3000:
            return "🔍 Overspend detected — review cost plan"

        # Within acceptable range
        return "✅ On track"

    except Exception as e:
        return f"⚠️ Reallocation check failed: {e}"
