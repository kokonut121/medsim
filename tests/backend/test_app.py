from fastapi.testclient import TestClient

from backend.db.iris_client import iris_client
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


def test_create_facility_route_geocodes_and_creates_unit(monkeypatch):
    async def fake_geocode(address: str, api_key: str):
        return {
            "address": "55 Fruit St, Boston, MA 02114, USA",
            "lat": 42.3626793,
            "lng": -71.0685514,
            "google_place_id": "place-mgh",
        }

    monkeypatch.setattr("backend.api.facilities.geocode_facility", fake_geocode)

    response = client.post(
        "/api/facilities",
        json={"name": "Massachusetts General Hospital", "address": "55 Fruit St, Boston, MA 02114", "unit_name": "Trauma Center"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["address"] == "55 Fruit St, Boston, MA 02114, USA"
    assert payload["google_place_id"] == "place-mgh"

    facility_id = payload["facility_id"]
    try:
        detail = client.get(f"/api/facilities/{facility_id}")
        assert detail.status_code == 200
        assert len(detail.json()["units"]) == 1
    finally:
        iris_client.delete_facility(facility_id)


def test_model_status_endpoint_for_seeded_model():
    response = client.get("/api/models/unit_1/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["unit_id"] == "unit_1"
