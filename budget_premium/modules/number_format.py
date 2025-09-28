
from typing import Literal, Optional

Scale = Literal["raw","k","m"]
def _scale_value(v: float, scale: Scale) -> float:
    if v is None: return v
    if scale == "k":
        return v/1_000
    if scale == "m":
        return v/1_000_000
    return v

def format_currency(value: Optional[float], scale: Scale="raw", decimals: int=2) -> str:
    if value is None: return ""
    v = _scale_value(float(value), scale)
    return f"{v:,.{decimals}f}"

def format_percent(value: Optional[float], decimals: int=2) -> str:
    if value is None: return ""
    return f"{float(value)*100:,.{decimals}f}%"

def apply_scale_series(s, scale: Scale="raw"):
    if scale == "raw": return s
    factor = 1_000 if scale == "k" else 1_000_000
    return s / factor
