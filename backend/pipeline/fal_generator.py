from __future__ import annotations

import asyncio
import base64

import httpx

from backend.config import get_settings


# ---------------------------------------------------------------------------
# Room-type prompts for coverage gap fill
# ---------------------------------------------------------------------------

_INTERIOR_PROMPTS: dict[str, str] = {
    "building_exterior": (
        "Exterior of a large modern hospital building, daytime, realistic photo, "
        "glass facade, ambulance bay visible, wide angle"
    ),
    "lobby_main_entrance": (
        "Hospital main lobby interior, reception desk, wayfinding signage, "
        "high ceilings, natural light, realistic photo"
    ),
    "ed_entrance_ambulance_bay": (
        "Hospital emergency department entrance, ambulance bay, sliding doors, "
        "overhead canopy, realistic photo, daytime"
    ),
    "corridor_hallway": (
        "Hospital corridor hallway, polished floor, fluorescent lighting, "
        "medical equipment along walls, realistic photo"
    ),
    "nursing_station": (
        "Hospital nursing station, central desk, computer monitors, medication carts, "
        "staff area, realistic photo"
    ),
    "patient_room": (
        "Hospital patient room interior, adjustable bed, IV pole, call light, "
        "window, clean and clinical, realistic photo"
    ),
    "medication_room_pharmacy": (
        "Hospital medication room, automated dispensing cabinet, shelving with "
        "labeled medications, secure door, realistic photo"
    ),
    "icu_bay": (
        "Hospital ICU bay, monitoring equipment, ventilator, overhead patient lift, "
        "glass partition, realistic photo"
    ),
    "operating_room": (
        "Hospital operating room, surgical table, overhead lights, instrument trays, "
        "sterile environment, realistic photo"
    ),
    "utility_support": (
        "Hospital utility room, clean linen carts, supply shelving, "
        "biohazard containers, realistic photo"
    ),
}

_FALLBACK_PROMPT = (
    "Hospital interior room, clinical environment, realistic photo, "
    "medical facility, natural lighting"
)


def _prompt_for(category: str) -> str:
    return _INTERIOR_PROMPTS.get(category, _FALLBACK_PROMPT)


# ---------------------------------------------------------------------------
# fal.ai helpers
# ---------------------------------------------------------------------------

async def _run_flux(prompt: str, fal_key: str, *, image_size: str = "landscape_4_3") -> bytes:
    """
    Submit a Flux Schnell request to fal.ai and return the image bytes.
    Uses the REST queue API directly so we stay async.
    """
    headers = {"Authorization": f"Key {fal_key}", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt,
        "image_size": image_size,
        "num_inference_steps": 4,
        "num_images": 1,
        "enable_safety_checker": False,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        # Submit
        submit = await client.post(
            "https://queue.fal.run/fal-ai/flux/schnell",
            headers=headers,
            json=payload,
        )
        submit.raise_for_status()
        request_id = submit.json()["request_id"]

        # Poll
        for _ in range(60):
            await asyncio.sleep(2)
            status = await client.get(
                f"https://queue.fal.run/fal-ai/flux/schnell/requests/{request_id}/status",
                headers=headers,
            )
            status.raise_for_status()
            if status.json().get("status") == "COMPLETED":
                break

        # Fetch result
        result = await client.get(
            f"https://queue.fal.run/fal-ai/flux/schnell/requests/{request_id}",
            headers=headers,
        )
        result.raise_for_status()
        image_url = result.json()["images"][0]["url"]

        # Download image bytes
        img_response = await client.get(image_url)
        img_response.raise_for_status()
        return img_response.content


def _synthetic_png(label: str) -> bytes:
    """1x1 transparent PNG used when fal.ai is not configured."""
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fill_coverage_gaps(gap_area_ids: list[str], facility_name: str) -> list[dict]:
    """
    For each missing room category in gap_area_ids, generate one synthetic
    interior image via fal.ai Flux Schnell.

    Returns a list of raw image dicts in the same shape as fetch_street_view /
    fetch_places_photos so they drop straight into acquire_images_for_facility.
    """
    settings = get_settings()

    if not gap_area_ids:
        return []

    if settings.use_synthetic_fallbacks or not settings.fal_key:
        return [
            {
                "bytes": _synthetic_png(category),
                "source": "supplemental_upload",
                "content_type": "image/png",
                "area_id": f"fal_gap_{category}",
                "file_name": f"fal-gap-{category}.png",
                "fal_generated": True,
                "category_hint": category,
            }
            for category in gap_area_ids
        ]

    async def _gen(category: str) -> dict:
        prompt = (
            f"{_prompt_for(category)}, {facility_name}, "
            "photorealistic, 8k, medical facility safety inspection"
        )
        image_bytes = await _run_flux(prompt, settings.fal_key)
        return {
            "bytes": image_bytes,
            "source": "supplemental_upload",
            "content_type": "image/jpeg",
            "area_id": f"fal_gap_{category}",
            "file_name": f"fal-gap-{category}.jpg",
            "fal_generated": True,
            "category_hint": category,
        }

    results = await asyncio.gather(*[_gen(cat) for cat in gap_area_ids], return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]


async def generate_floor_plan(scene_graph: dict, facility_name: str) -> bytes:
    """
    Generate a 2D architectural floor plan diagram from the scene graph.
    Returns raw image bytes (JPEG or synthetic PNG).
    """
    settings = get_settings()

    if settings.use_synthetic_fallbacks or not settings.fal_key:
        return _synthetic_png("floor_plan")

    # Build a descriptive prompt from the scene graph
    rooms = []
    for unit in scene_graph.get("units", []):
        unit_type = unit.get("unit_type", "unit")
        for room in unit.get("rooms", []):
            rooms.append(f"{room.get('type', 'room')} {room.get('room_id', '')}")

    room_summary = ", ".join(rooms[:12]) or "patient rooms, nursing station, corridors"
    flow = scene_graph.get("flow_annotations", {})
    clean = ", ".join(flow.get("clean_corridors", []))
    dirty = ", ".join(flow.get("dirty_corridors", []))

    prompt = (
        f"Architectural floor plan of {facility_name} hospital, top-down 2D view, "
        f"rooms labeled: {room_summary}. "
        f"Clean corridors: {clean or 'marked in blue'}. "
        f"Dirty corridors: {dirty or 'marked in red'}. "
        "Blueprint style, clean line drawing, white background, professional architectural diagram, "
        "room dimensions visible, medical facility layout"
    )

    return await _run_flux(prompt, settings.fal_key, image_size="square_hd")
