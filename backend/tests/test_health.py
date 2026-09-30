from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_database_and_extensions():
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"]["connected"] is True
    assert set(body["database"]["extensions"]) == {"postgis", "vector", "pg_trgm"}
    assert all(body["database"]["extensions"].values())
