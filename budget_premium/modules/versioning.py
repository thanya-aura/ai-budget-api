def compare_versions(df1, df2):
    return df1.merge(df2, on=["Cost Center", "Project"], suffixes=("_V1", "_V2"))