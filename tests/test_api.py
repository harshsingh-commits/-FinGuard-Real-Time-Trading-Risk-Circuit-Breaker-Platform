import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from fastapi.testclient import TestClient
from fin_guard.api.main import app


def test_api_health_and_simulation_endpoints():
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    response = client.post("/simulate-market", json={"scenario": "normal"})
    assert response.status_code == 200
    assert "risk_score" in response.json()
    assert client.get("/checkpoints").status_code == 200
