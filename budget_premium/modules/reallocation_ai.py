def suggest_reallocation(row):
    if row["Variance"] > 3000:
        return "💡 Consider reallocating from surplus"
    elif row["Variance"] < -3000:
        return "🔍 Overspend detected"
    return "OK"