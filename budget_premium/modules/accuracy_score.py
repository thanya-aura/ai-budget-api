def compute_accuracy_score(df):
    avg_abs_var = df["Variance"].abs().mean()
    score = max(0, 100 - avg_abs_var / 100)
    return round(score, 2)