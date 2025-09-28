import io
import pandas as pd

# ✅ ใช้ package import หลังจากเพิ่ม __init__.py ใน budget_plus/, utils/, tests/
from budget_plus.utils.number_format_utils import format_number
from budget_plus.pdf_summary import generate_pdf_with_chart

def test_format_number_basic():
    """ตรวจว่า format_number แสดงผลถูกต้อง"""
    assert format_number(1234.567, "number") == "1,234.57"
    assert format_number(0.1234, "percent") == "12.34%"
    assert format_number(1234, "k") == "1.23K"
    assert format_number(1_234_567, "m") == "1.23M"

def test_format_number_invalid():
    """ตรวจว่า input ไม่ใช่เลข → คืนค่า string เดิม"""
    assert format_number("abc", "number") == "abc"
    assert format_number(None, "number") == "None"

def test_generate_pdf_with_chart(tmp_path):
    """ตรวจว่า generate_pdf_with_chart สร้าง PDF ได้"""
    df = pd.DataFrame({
        "Cost Center": ["A", "B"],
        "Planned": [1000, 2000],
        "FX Adjusted Actual": [1100, 1900],
        "Variance": [100, -100],
        "Margin": [0.1, 0.2],   # 10%, 20%
    })

    buffer = generate_pdf_with_chart(df, include_percent=True)
    assert isinstance(buffer, io.BytesIO)

    content = buffer.getvalue()
    # ✅ PDF ต้องไม่ว่าง และมีขนาดมากกว่า 1KB
    assert len(content) > 1000
