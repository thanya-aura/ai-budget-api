def compute_accuracy_score(df):
    """
    Compute an overall accuracy score based on average absolute variance.

    The logic penalizes larger variances and caps the score between 0 and 100.

    Parameters:
    - df (pd.DataFrame): Must contain a "Variance" column.

    Returns:
    - float: Accuracy score between 0 and 100.
    """
    try:
        if "Variance" not in df.columns:
            raise ValueError("Missing 'Variance' column for accuracy calculation.")

        avg_abs_var = df["Variance"].abs().mean()
        score = max(0, 100 - avg_abs_var / 100)
        return round(score, 2)

    except Exception as e:
        # Fallback score or log if needed
        print(f"⚠️ Error computing accuracy score: {e}")
        return 0.0
