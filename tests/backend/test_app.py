from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_healthcheck():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_facilities_endpoint():
    response = client.get("/api/facilities")
    assert response.status_code == 200
    assert len(response.json()) >= 1

