"""
Pipeline stage tests — all external HTTP calls are mocked.
No Google, World Labs, or R2 credentials required.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from backend.pipeline.scene_graph import extract_scene_graph
from backend.pipeline.classify import classify_image
from backend.pipeline.image_acquisition import fetch_street_view, fetch_places_photos
from backend.pipeline.world_model import (
    PROMPT_IMAGE_LIMIT,
    _pick_prompt_images,
    _response_error_detail,
    _world_prompt_from_images,
    generate_world_model,
)


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


def make_source_images(source: str, n: int) -> list[dict]:
    images = []
    for i in range(n):
        image = {
            "image_id": f"{source}_{i}",
            "source": source,
            "public_url": f"https://r2.example.com/{source}_{i}.jpg",
        }
        if source == "vr_video":
            image["timestamp_s"] = i * 2.5
        else:
            image["heading"] = (i * 30) % 360
        images.append(image)
    return images


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
# Classification — synthetic path (classify_image is per-image)
# ---------------------------------------------------------------------------

def test_classify_image_street_view():
    result = asyncio.get_event_loop().run_until_complete(
        classify_image(b"fake-jpeg", "street_view", {"heading": 0})
    )
    assert result["category"] == "building_exterior"
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["source"] == "street_view"


def test_classify_image_places():
    result = asyncio.get_event_loop().run_until_complete(
        classify_image(b"fake-jpeg", "places", {"index": 1})
    )
    assert result["category"] == "lobby_main_entrance"
    assert 0.0 <= result["confidence"] <= 1.0


def test_classify_image_ed_entrance_heading():
    result = asyncio.get_event_loop().run_until_complete(
        classify_image(b"fake-jpeg", "street_view", {"heading": 180})
    )
    assert result["category"] == "ed_entrance_ambulance_bay"


def test_classify_image_supplemental_upload():
    result = asyncio.get_event_loop().run_until_complete(
        classify_image(b"fake-jpeg", "supplemental_upload", {})
    )
    assert result["category"] == "patient_room"


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

def test_pick_prompt_images_evenly_samples_long_vr_video():
    images = make_source_images("vr_video", 24)

    selected = _pick_prompt_images(images)

    assert len(selected) == PROMPT_IMAGE_LIMIT
    indices = [int(image["image_id"].rsplit("_", 1)[1]) for image in selected]
    assert indices[0] == 0
    assert indices[-1] == 23
    assert max(indices) > PROMPT_IMAGE_LIMIT


def test_pick_prompt_images_blends_places_and_street_view():
    images = make_source_images("places", 10) + make_source_images("street_view", 10)

    selected = _pick_prompt_images(images)

    assert len(selected) == PROMPT_IMAGE_LIMIT
    sources = {image["source"] for image in selected}
    assert sources == {"places", "street_view"}
    assert sum(1 for image in selected if image["source"] == "places") > sum(
        1 for image in selected if image["source"] == "street_view"
    )


def test_world_prompt_respects_world_labs_reconstruct_limit():
    images = make_source_images("vr_video", 20)

    prompt = _world_prompt_from_images(images, {"units": [], "flow_annotations": {}})

    assert prompt["reconstruct_images"] is True
    assert len(prompt["multi_image_prompt"]) == PROMPT_IMAGE_LIMIT
    assert PROMPT_IMAGE_LIMIT == 8


def test_response_error_detail_prefers_detail_payload():
    response = httpx.Response(
        400,
        json={"detail": [{"loc": ["body", "world_prompt"], "msg": "too many images"}]},
    )

    detail = _response_error_detail(response)

    assert "too many images" in detail


def test_generate_world_model_synthetic_fallback(monkeypatch):
    monkeypatch.setenv("MEDSIM_USE_SYNTHETIC_FALLBACKS", "true")
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
    monkeypatch.setenv("MEDSIM_USE_SYNTHETIC_FALLBACKS", "true")
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
