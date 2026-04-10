"""
Pipeline stage tests — all external HTTP calls are mocked.
No Google, World Labs, or R2 credentials required.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from backend.pipeline.scene_graph import extract_scene_graph
from backend.pipeline.classify import classify_images
from backend.pipeline.image_acquisition import fetch_street_view, fetch_places_photos
from backend.pipeline.world_model import generate_world_model


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_classified_images(n: int = 4) -> list[dict]:
    return [
        {
            "image_id": f"img_{i}",
            "source": "street_view",
            "public_url": f"https://r2.example.com/img_{i}.jpg",
            "category": "patient_room",
            "confidence": 0.85,
            "heading": i * 45,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Image acquisition — synthetic path (no API key)
# ---------------------------------------------------------------------------

def test_fetch_street_view_synthetic_returns_eight_headings():
    images = asyncio.get_event_loop().run_until_complete(
        fetch_street_view(42.36, -71.07, api_key="")
    )
    assert len(images) == 8
    headings = {img["heading"] for img in images}
    assert headings == {0, 45, 90, 135, 180, 225, 270, 315}


def test_fetch_street_view_synthetic_source_tag():
    images = asyncio.get_event_loop().run_until_complete(
        fetch_street_view(42.36, -71.07, api_key="")
    )
    for img in images:
        assert img["source"] == "street_view"
        assert img["bytes"]


def test_fetch_places_photos_synthetic_returns_images():
    images = asyncio.get_event_loop().run_until_complete(
        fetch_places_photos("place-mgh", api_key="")
    )
    assert isinstance(images, list)
    for img in images:
        assert img["source"] == "places"


# ---------------------------------------------------------------------------
# Classification — synthetic path
# ---------------------------------------------------------------------------

def test_classify_images_returns_one_result_per_input():
    raw = [
        {"bytes": b"fake-jpeg-data", "source": "street_view", "heading": 0,
         "content_type": "image/jpeg", "area_id": "sv_0", "file_name": "sv-0.jpg"}
    ]
    results = asyncio.get_event_loop().run_until_complete(
        classify_images(raw, facility_id="fac_test", api_key="")
    )
    assert len(results) == len(raw)


def test_classify_images_schema():
    raw = [
        {"bytes": b"fake", "source": "street_view", "heading": h,
         "content_type": "image/jpeg", "area_id": f"sv_{h}", "file_name": f"sv-{h}.jpg"}
        for h in [0, 90]
    ]
    results = asyncio.get_event_loop().run_until_complete(
        classify_images(raw, facility_id="fac_test", api_key="")
    )
    for r in results:
        assert "category" in r
        assert "confidence" in r
        assert 0.0 <= r["confidence"] <= 1.0
        assert "public_url" in r


# ---------------------------------------------------------------------------
# Scene graph
# ---------------------------------------------------------------------------

def test_extract_scene_graph_produces_rooms():
    images = make_classified_images(4)
    graph = asyncio.get_event_loop().run_until_complete(
        extract_scene_graph(images, osm_topology={})
    )
    assert "units" in graph
    rooms = graph["units"][0]["rooms"]
    assert len(rooms) == 4


def test_extract_scene_graph_flow_annotations_present():
    images = make_classified_images(3)
    graph = asyncio.get_event_loop().run_until_complete(
        extract_scene_graph(images, osm_topology={})
    )
    fa = graph["flow_annotations"]
    assert "patient_flow_paths" in fa
    assert "staff_flow_paths" in fa
    assert "clean_corridors" in fa
    assert "dirty_corridors" in fa


def test_extract_scene_graph_room_ids_are_unique():
    images = make_classified_images(6)
    graph = asyncio.get_event_loop().run_until_complete(
        extract_scene_graph(images, osm_topology={})
    )
    room_ids = [r["room_id"] for r in graph["units"][0]["rooms"]]
    assert len(room_ids) == len(set(room_ids))


def test_extract_scene_graph_handles_empty_images():
    graph = asyncio.get_event_loop().run_until_complete(
        extract_scene_graph([], osm_topology={})
    )
    assert graph["units"][0]["rooms"] == []


# ---------------------------------------------------------------------------
# World model — synthetic fallback (no World Labs key)
# ---------------------------------------------------------------------------

def test_generate_world_model_synthetic_fallback(monkeypatch):
    monkeypatch.setenv("MEDSENTINEL_USE_SYNTHETIC_FALLBACKS", "true")
    # Reset cached settings so env var takes effect
    from backend.config import get_settings
    get_settings.cache_clear()

    images = make_classified_images(4)
    graph = {"units": [], "flow_annotations": {}}
    result = asyncio.get_event_loop().run_until_complete(
        generate_world_model(
            images, graph,
            facility_id="fac_test",
            facility_name="Test Hospital",
        )
    )
    assert result["world_id"].startswith("world_")
    assert result["splat_url"].endswith(".spz")
    assert result["source_image_count"] == 4

    # Restore
    get_settings.cache_clear()


def test_generate_world_model_synthetic_is_deterministic(monkeypatch):
    monkeypatch.setenv("MEDSENTINEL_USE_SYNTHETIC_FALLBACKS", "true")
    from backend.config import get_settings
    get_settings.cache_clear()

    images = make_classified_images(4)
    graph = {}
    r1 = asyncio.get_event_loop().run_until_complete(
        generate_world_model(images, graph, facility_id="fac_det", facility_name="Det Hospital")
    )
    r2 = asyncio.get_event_loop().run_until_complete(
        generate_world_model(images, graph, facility_id="fac_det", facility_name="Det Hospital")
    )
    assert r1["world_id"] == r2["world_id"]

    get_settings.cache_clear()
