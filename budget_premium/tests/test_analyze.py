from fastapi.testclient import TestClient
from main_legacy import app
from io import BytesIO
import pandas as pd

client = TestClient(app)

def test_analyze_endpoint():
    # Prepare test input DataFrame
    df = pd.DataFrame({
        "Planned": [10000],
        "Actual": [12000],
        "FX Rate": [1.0],
        "Cost Center": ["Sales"],
        "Project": ["Expansion"],
        "Driver": [5]
    })

    # Save to Excel in-memory
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)

    # POST to the /analyze endpoint
    response = client.post(
        "/analyze",
        files={"file": ("sample.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

    # ✅ Validate JSON response
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    # ✅ Parse and validate fields
    result = response.json()
    assert isinstance(result, list)
    assert "Variance" in result[0]
    assert "Adjusted Actual" in result[0]
    assert "Accuracy Score" in result[0]
    assert "Reallocation Advice" in result[0]
    assert "Driver Forecast" in result[0]
    assert result[0]["Variance"] == 2000
    assert result[0]["Driver Forecast"] == 50000
