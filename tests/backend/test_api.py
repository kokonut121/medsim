"""
Full API endpoint coverage — facilities, models, scans, findings, reports.
Uses the shared TestClient fixture from conftest.py.
No external API keys required.
"""
from __future__ import annotations

import asyncio

import pytest

from backend.db.iris_client import iris_client


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_healthcheck(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Facilities
# ---------------------------------------------------------------------------

def test_list_facilities_returns_demo_seed(client):
    r = client.get("/api/facilities")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1


def test_create_facility(client, monkeypatch):
    async def fake_geocode(address, api_key):
        return {
            "address": "55 Fruit St, Boston, MA 02114, USA",
            "lat": 42.3626793,
            "lng": -71.0685514,
            "google_place_id": "place-mgh",
        }
    monkeypatch.setattr("backend.api.facilities.geocode_facility", fake_geocode)

    r = client.post("/api/facilities", json={
        "name": "Massachusetts General Hospital",
        "address": "55 Fruit St, Boston, MA 02114",
        "unit_name": "Trauma Center",
    })
    assert r.status_code == 200
    payload = r.json()
    assert payload["google_place_id"] == "place-mgh"
    assert payload["address"] == "55 Fruit St, Boston, MA 02114, USA"

    # cleanup
    iris_client.delete_facility(payload["facility_id"])


def test_get_facility_detail(client):
    r = client.get("/api/facilities/fac_demo")
    assert r.status_code == 200
    data = r.json()
    assert "facility" in data
    assert "units" in data
    assert len(data["units"]) >= 1


def test_get_facility_coverage(client):
    r = client.get("/api/facilities/fac_demo/coverage")
    assert r.status_code == 200
    data = r.json()
    assert "covered_areas" in data
    assert "gap_areas" in data


def test_get_nonexistent_facility_returns_404(client):
    r = client.get("/api/facilities/fac_does_not_exist")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# World model status
# ---------------------------------------------------------------------------

def test_model_status_for_seeded_unit(client):
    r = client.get("/api/models/unit_1/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ready"
    assert data["unit_id"] == "unit_1"


def test_model_status_for_unknown_unit_returns_404(client):
    r = client.get("/api/models/unit_does_not_exist/status")
    assert r.status_code == 404


def test_video_extract_endpoint_processes_without_invalid_status(client, fresh_iris, monkeypatch):
    monkeypatch.setattr(
        "backend.api.video.extract_frames",
        lambda *_args, **_kwargs: [
            {
                "source": "vr_video",
                "file_name": "frame_000001.jpg",
                "bytes": b"jpeg-bytes",
                "content_type": "image/jpeg",
                "heading": None,
            }
        ],
    )

    async def fake_classify_image(_image_bytes, _source, _context):
        return {
            "category": "corridor_hallway",
            "confidence": 0.91,
            "notes": "clear corridor",
        }

    async def fake_extract_scene_graph(_classified, _osm):
        return {
            "units": [{"unit_id": "unit_1", "rooms": []}],
            "flow_annotations": {},
        }

    async def fake_generate_world_model(_images, scene_graph, *, facility_id, facility_name):
        return {
            "world_id": "world_test",
            "splat_url": f"facilities/{facility_id}/models/world_test/scene.spz",
            "scene_manifest": scene_graph,
            "source_image_count": 1,
            "caption": f"{facility_name} walkthrough model",
        }

    monkeypatch.setattr("backend.api.video.classify_image", fake_classify_image)
    monkeypatch.setattr("backend.api.video.extract_scene_graph", fake_extract_scene_graph)
    monkeypatch.setattr("backend.api.video.generate_world_model", fake_generate_world_model)
    monkeypatch.setattr(
        "backend.api.video._store_video_frame",
        lambda key, payload, *, content_type: f"/api/fal-images/{key.replace('/', '_')}",
    )

    response = client.post(
        "/api/video/extract/fac_demo?max_frames=12&equirect_crops=0",
        files={"file": ("walkthrough.mov", b"x" * 2048, "video/quicktime")},
    )

    assert response.status_code == 200
    payload = response.json()
    model = fresh_iris.models[payload["model_id"]]
    assert model.status == "ready"
    assert model.source_image_count == 1
    assert model.caption == "LeTourneau University — Nursing Skills Lab walkthrough model"


def test_process_video_offloads_blocking_frame_work(fresh_iris, monkeypatch):
    import backend.api.video as video_api

    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    model = fresh_iris.create_or_replace_model("fac_demo", status="queued")

    def fake_extract_frames(*args, **kwargs):
        return [
            {
                "source": "vr_video",
                "file_name": "frame_000001.jpg",
                "bytes": b"jpeg-bytes",
                "content_type": "image/jpeg",
                "heading": None,
            }
        ]

    def fake_store_video_frame(*args, **kwargs):
        return "/api/fal-images/frame_000001.jpg"

    async def fake_classify_image(_image_bytes, _source, _context):
        return {
            "category": "corridor_hallway",
            "confidence": 0.91,
            "notes": "clear corridor",
        }

    async def fake_extract_scene_graph(_classified, _osm):
        return {"units": [{"unit_id": "unit_1", "rooms": []}], "flow_annotations": {}}

    async def fake_generate_world_model(_images, scene_graph, *, facility_id, facility_name):
        return {
            "world_id": "world_threaded",
            "splat_url": f"facilities/{facility_id}/models/world_threaded/scene.spz",
            "scene_manifest": scene_graph,
            "source_image_count": 1,
            "caption": f"{facility_name} walkthrough model",
        }

    async def fake_to_thread(func, /, *args, **kwargs):
        calls.append((func.__name__, args, kwargs))
        return func(*args, **kwargs)

    monkeypatch.setattr(video_api, "extract_frames", fake_extract_frames)
    monkeypatch.setattr(video_api, "_store_video_frame", fake_store_video_frame)
    monkeypatch.setattr(video_api, "classify_image", fake_classify_image)
    monkeypatch.setattr(video_api, "extract_scene_graph", fake_extract_scene_graph)
    monkeypatch.setattr(video_api, "generate_world_model", fake_generate_world_model)
    monkeypatch.setattr(video_api.asyncio, "to_thread", fake_to_thread)

    asyncio.run(
        video_api._process_video(
            "fac_demo",
            model.model_id,
            b"x" * 2048,
            max_frames=8,
            equirect_crops=0,
        )
    )

    assert [name for name, _args, _kwargs in calls] == ["fake_extract_frames", "fake_store_video_frame"]
    model = fresh_iris.models[model.model_id]
    assert model.status == "ready"


# ---------------------------------------------------------------------------
# Scans
# ---------------------------------------------------------------------------

def _run_scan_for_unit(unit_id="unit_1"):
    from backend.agents.orchestrator import run_scan
    return asyncio.get_event_loop().run_until_complete(run_scan(unit_id, "model_unit_1"))


def test_trigger_scan_endpoint(client):
    r = client.post("/api/scans/unit_1/run")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "complete"
    assert data["unit_id"] == "unit_1"


def test_scan_status_endpoint_after_scan(client):
    client.post("/api/scans/unit_1/run")
    r = client.get("/api/scans/unit_1/status")
    assert r.status_code == 200
    assert r.json()["status"] == "complete"


def test_scan_status_unknown_unit_returns_404(client):
    r = client.get("/api/scans/unit_ghost/status")
    assert r.status_code == 404


def test_trigger_scan_on_non_ready_model_returns_409(client, monkeypatch):
    from backend.db.iris_client import iris_client as ic
    model = ic.get_model("unit_1")
    # Temporarily mark model as queued
    ic.update_model(model.model_id, status="queued")
    r = client.post("/api/scans/unit_1/run")
    assert r.status_code == 409
    # Restore
    ic.update_model(model.model_id, status="ready")


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def test_get_findings_after_scan(client):
    client.post("/api/scans/unit_1/run")
    r = client.get("/api/scans/unit_1/findings")
    assert r.status_code == 200
    findings = r.json()
    assert len(findings) >= 6  # at least one per domain


def test_get_findings_filter_by_domain(client):
    client.post("/api/scans/unit_1/run")
    r = client.get("/api/scans/unit_1/findings?domain=ERA")
    assert r.status_code == 200
    for f in r.json():
        assert f["domain"] == "ERA"


def test_get_findings_filter_by_severity(client):
    client.post("/api/scans/unit_1/run")
    r = client.get("/api/scans/unit_1/findings?severity=CRITICAL")
    assert r.status_code == 200
    for f in r.json():
        assert f["severity"] == "CRITICAL"


def test_get_single_finding(client):
    client.post("/api/scans/unit_1/run")
    findings = client.get("/api/scans/unit_1/findings").json()
    finding_id = findings[0]["finding_id"]

    r = client.get(f"/api/scans/unit_1/findings/{finding_id}")
    assert r.status_code == 200
    assert r.json()["finding_id"] == finding_id


def test_get_nonexistent_finding_returns_404(client):
    r = client.get("/api/scans/unit_1/findings/finding_does_not_exist")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def test_pdf_report_after_scan(client):
    client.post("/api/scans/unit_1/run")
    r = client.get("/api/reports/unit_1/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert len(r.content) > 100  # non-empty PDF


def test_manifest_report_after_scan(client):
    client.post("/api/scans/unit_1/run")
    r = client.get("/api/reports/unit_1/manifest")
    assert r.status_code == 200
    data = r.json()
    assert "scan_id" in data
    assert "findings" in data
    assert len(data["findings"]) >= 1


def test_pdf_report_before_scan_returns_404(client, fresh_iris):
    r = client.get("/api/reports/unit_1/pdf")
    assert r.status_code == 404
