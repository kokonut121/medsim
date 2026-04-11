from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.db.iris_client import FHIRServiceIRISClient, iris_client
from backend.main import app
from backend.models import DomainStatus, Finding, Scan, SpatialAnchor
from backend.reports.fhir_projector import fhir_safe_id


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


def test_fhir_routes_return_synthetic_projection_for_completed_scan():
    scan_response = client.post("/api/scans/unit_1/run")
    assert scan_response.status_code == 200
    scan = scan_response.json()

    report_response = client.get(f"/api/fhir/DiagnosticReport/{scan['scan_id']}")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["resourceType"] == "DiagnosticReport"
    assert report["id"] == fhir_safe_id(scan["scan_id"])

    observation_response = client.get(f"/api/fhir/Observation/{scan['findings'][0]['finding_id']}")
    assert observation_response.status_code == 200
    observation = observation_response.json()
    assert observation["resourceType"] == "Observation"
    assert observation["id"] == fhir_safe_id(scan["findings"][0]["finding_id"])


def test_fhir_service_client_falls_back_to_synthetic_projection(monkeypatch):
    settings = Settings(
        _env_file=None,
        MEDSENTINEL_IRIS_MODE="fhir",
        IRIS_FHIR_BASE="http://example.test/fhir/r4",
        IRIS_USER="medsent_app",
        IRIS_PASSWORD="changeme",
    )
    client = FHIRServiceIRISClient(settings)
    monkeypatch.setattr(client._fhir_repository, "put_resource", lambda resource: resource)

    finding = Finding(
        finding_id="finding_demo",
        scan_id="scan_demo",
        domain="ERA",
        sub_agent="response-cart",
        room_id="R101",
        severity="HIGH",
        compound_severity=0.8,
        label_text="Crash cart access obstructed",
        spatial_anchor=SpatialAnchor(x=1.0, y=2.0, z=3.0),
        confidence=0.9,
        evidence_r2_keys=[],
        recommendation="Clear the corridor around the crash cart",
        compound_domains=["ERA"],
        created_at=datetime.now(timezone.utc),
    )
    scan = Scan(
        scan_id="scan_demo",
        unit_id="unit_1",
        status="complete",
        domain_statuses={
            "ERA": DomainStatus(status="complete", finding_count=1),
            "ICA": DomainStatus(status="complete", finding_count=0),
            "MSA": DomainStatus(status="complete", finding_count=0),
            "FRA": DomainStatus(status="complete", finding_count=0),
            "PFA": DomainStatus(status="complete", finding_count=0),
            "SCA": DomainStatus(status="complete", finding_count=0),
        },
        findings=[finding],
        triggered_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    client.write_findings(scan, [finding])

    def fail_lookup(*args, **kwargs):
        raise RuntimeError("FHIR repository unavailable")

    monkeypatch.setattr(client._fhir_repository, "get_resource", fail_lookup)

    report = client.get_diagnostic_report_resource("scan_demo")
    observation = client.get_observation_resource("finding_demo")

    assert report["resourceType"] == "DiagnosticReport"
    assert report["id"] == fhir_safe_id("scan_demo")
    assert observation["resourceType"] == "Observation"
    assert observation["id"] == fhir_safe_id("finding_demo")
