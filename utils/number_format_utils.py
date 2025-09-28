def format_number(value, style="number"):
    """
    Format number into different styles:
    - "number" : xxx,xxx.xx
    - "percent": xx.xx%
    - "k"      : xx.xxK
    - "m"      : xx.xxM
    """
    try:
        val = float(value)
    except (ValueError, TypeError):
        return str(value)

    if style == "percent":
        return f"{val:.2%}"                # 0.1234 → 12.34%
    elif style == "k":
        return f"{val/1_000:.2f}K"         # 12,345 → 12.35K
    elif style == "m":
        return f"{val/1_000_000:.2f}M"     # 12,345,678 → 12.35M
    else:
        return f"{val:,.2f}"               # 12345.6 → 12,345.60
