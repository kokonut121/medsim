from __future__ import annotations

import asyncio
import base64
import io
import os

import fal_client
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
    """Text-to-image via Flux Schnell."""
    os.environ["FAL_KEY"] = fal_key

    handler = await fal_client.submit_async(
        "fal-ai/flux/schnell",
        arguments={
            "prompt": prompt,
            "image_size": image_size,
            "num_inference_steps": 4,
            "num_images": 1,
            "enable_safety_checker": False,
        },
    )
    result = await handler.get()
    image_url = result["images"][0]["url"]

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(image_url)
        response.raise_for_status()
        return response.content


async def _upload_reference(image_bytes: bytes, fal_key: str) -> str:
    """Upload bytes to fal.ai storage and return a CDN URL for use as image_url."""
    os.environ["FAL_KEY"] = fal_key
    url = await asyncio.to_thread(fal_client.upload, io.BytesIO(image_bytes), "image/jpeg")
    return url


async def _run_flux_img2img(
    prompt: str,
    reference_url: str,
    fal_key: str,
    *,
    strength: float = 0.75,
) -> bytes:
    """Image-to-image via Flux Dev — generates a new angle conditioned on a reference photo."""
    os.environ["FAL_KEY"] = fal_key

    handler = await fal_client.submit_async(
        "fal-ai/flux/dev/image-to-image",
        arguments={
            "prompt": prompt,
            "image_url": reference_url,
            "strength": strength,
            "num_inference_steps": 28,
            "num_images": 1,
            "enable_safety_checker": False,
        },
    )
    result = await handler.get()
    image_url = result["images"][0]["url"]

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(image_url)
        response.raise_for_status()
        return response.content


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


async def generate_floor_plan(scene_graph: dict, facility_name: str, *, prompt_override: str | None = None) -> bytes:
    """
    Generate a 2D architectural floor plan diagram from the scene graph.
    Returns raw image bytes (JPEG or synthetic PNG).
    """
    settings = get_settings()

    if settings.use_synthetic_fallbacks or not settings.fal_key:
        return _synthetic_png("floor_plan")

    if prompt_override:
        return await _run_flux(prompt_override, settings.fal_key, image_size="square_hd")

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


# ---------------------------------------------------------------------------
# Multi-angle view generation for world modeling
# ---------------------------------------------------------------------------

_ANGLE_SHOTS: list[dict] = [
    # Exterior cardinal angles
    {"label": "exterior_north",     "heading": 0,   "prompt": "Hospital building exterior, north facade, street level, realistic photo, daytime"},
    {"label": "exterior_east",      "heading": 90,  "prompt": "Hospital building exterior, east facade, street level, realistic photo, daytime"},
    {"label": "exterior_south",     "heading": 180, "prompt": "Hospital building exterior, south facade, street level, realistic photo, daytime"},
    {"label": "exterior_west",      "heading": 270, "prompt": "Hospital building exterior, west facade, street level, realistic photo, daytime"},
    # Elevated / aerial
    {"label": "aerial_45",          "heading": 0,   "prompt": "Hospital complex aerial view 45-degree angle, drone perspective, rooftop visible, ambulance bay, realistic"},
    {"label": "aerial_overhead",    "heading": 0,   "prompt": "Hospital building directly overhead bird's-eye aerial view, rooftop HVAC, helipads, realistic satellite photo"},
    # Interior multi-angle
    {"label": "interior_trauma_overhead", "heading": None, "prompt": "Hospital trauma bay interior, overhead looking straight down, patient gurney, ceiling lights, equipment, realistic photo"},
    {"label": "interior_corridor_wide",   "heading": None, "prompt": "Hospital trauma corridor, wide-angle fisheye view, both walls visible, equipment bays, realistic photo"},
    {"label": "interior_ns_isometric",    "heading": None, "prompt": "Hospital nursing station, isometric 3/4 angle view, desk area, monitors, medication carts, realistic photo"},
    {"label": "interior_resus_corner",    "heading": None, "prompt": "Hospital resuscitation room, corner perspective, crash cart, defibrillator, ceiling mounted lights, realistic photo"},
    # Low angle / ground level detail
    {"label": "entrance_low_angle",       "heading": None, "prompt": "Hospital emergency entrance, low camera angle, automatic doors, overhead signage, ambulance ramp, realistic photo"},
    {"label": "ambulance_bay_wide",       "heading": None, "prompt": "Hospital ambulance bay, wide angle, multiple bays, overhead doors, dock levelers, realistic photo"},
]


async def generate_multi_angle_views(
    facility_name: str,
    *,
    labels: list[str] | None = None,
    reference_images: list[bytes] | None = None,
) -> list[dict]:
    """
    Generate multi-angle views of a facility using fal.ai.

    When reference_images are provided (actual uploaded photos), uses Flux Dev
    image-to-image so each generated view is visually grounded in the real space.
    Falls back to text-to-image (Flux Schnell) when no references are available.

    Returns list of image dicts compatible with the acquisition pipeline schema.
    """
    settings = get_settings()
    shots = [s for s in _ANGLE_SHOTS if labels is None or s["label"] in labels]

    if settings.use_synthetic_fallbacks or not settings.fal_key:
        return [
            {
                "bytes": _synthetic_png(shot["label"]),
                "source": "supplemental_upload",
                "content_type": "image/png",
                "file_name": f"fal-angle-{shot['label']}.png",
                "heading": shot["heading"],
                "label": shot["label"],
                "fal_generated": True,
            }
            for shot in shots
        ]

    # Upload one reference image to fal.ai storage so all shots can reuse the URL
    ref_url: str | None = None
    if reference_images:
        try:
            ref_url = await _upload_reference(reference_images[0], settings.fal_key)
        except Exception:
            ref_url = None

    async def _gen(shot: dict) -> dict:
        prompt = f"{shot['prompt']}, {facility_name}, photorealistic, 8k, high detail"
        if ref_url:
            image_bytes = await _run_flux_img2img(prompt, ref_url, settings.fal_key, strength=0.70)
        else:
            image_bytes = await _run_flux(prompt, settings.fal_key, image_size="landscape_4_3")
        return {
            "bytes": image_bytes,
            "source": "supplemental_upload",
            "content_type": "image/jpeg",
            "file_name": f"fal-angle-{shot['label']}.jpg",
            "heading": shot["heading"],
            "label": shot["label"],
            "fal_generated": True,
        }

    results = await asyncio.gather(*[_gen(s) for s in shots], return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]
