import pandas as pd
from io import BytesIO
from fastapi.testclient import TestClient
import sys
import os

# Ensure main app can be imported correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main_legacy import app

client = TestClient(app)

def test_premium_analysis():
    df = pd.DataFrame({
        "Version": ["V1"],
        "Scenario": ["Best"],
        "Cost Center": ["R&D"],
        "Project": ["AI Upgrade"],
        "Planned": [50000],
        "Actual": [55000],
        "FX Rate": [1.1],
        "CapEx/OpEx": ["CapEx"],
        "Cost Type": ["Hardware"],
        "Owner": ["alice"],
        "Approval Status": ["Approved"]
    })

    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    response = client.post(
        "/analyze",
        files={"file": ("premium_test.xlsx", buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"

    try:
        result = response.json()
    except Exception as e:
        raise AssertionError(f"Expected JSON response but got error: {e}\nRaw content: {response.content}")

    assert isinstance(result, list)
    assert "Variance" in result[0]
