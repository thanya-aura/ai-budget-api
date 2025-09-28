import pandas as pd
from io import BytesIO
from fastapi.testclient import TestClient
from main_legacy import app

client = TestClient(app)

def test_analyze():
    df = pd.DataFrame({
        "Planned": [10000],
        "Actual": [12000],
        "FX Rate": [1.0],
        "Cost Center": ["Sales"],
        "Project": ["AI"],
        "Driver": [2],
        "Scenario": ["Base"]
    })
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    response = client.post("/analyze", files={"file": ("test.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert response.status_code == 200
    result = response.json()
    assert result[0]["Variance"] == 2000