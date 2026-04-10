from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.config import get_settings
from backend.db.iris_client import iris_client
from backend.db.r2_client import r2_client
from backend.jobs.acquire_images import acquire_images_for_facility, _store_fal_image, _fal_public_url
from backend.models import FacilityCreate, ImageMeta
from backend.pipeline.facility_lookup import geocode_facility
from backend.pipeline.fal_generator import generate_multi_angle_views

_ANGLE_LABELS = {
    "exterior_north", "exterior_east", "exterior_south", "exterior_west",
    "aerial_45", "aerial_overhead",
    "interior_trauma_overhead", "interior_corridor_wide",
    "interior_ns_isometric", "interior_resus_corner",
    "entrance_low_angle", "ambulance_bay_wide",
}


router = APIRouter(prefix="/api/facilities", tags=["facilities"])


@router.get("")
async def list_facilities():
    return iris_client.list_facilities()


@router.post("")
async def create_facility(payload: FacilityCreate):
    settings = get_settings()
    if settings.use_synthetic_fallbacks and not settings.google_api_key:
        return iris_client.create_facility(payload)
    resolved = await geocode_facility(payload.address, settings.google_api_key)
    return iris_client.create_facility(
        payload.model_copy(
            update={
                "address": resolved["address"],
                "lat": resolved["lat"],
                "lng": resolved["lng"],
                "google_place_id": resolved["google_place_id"],
            }
        )
    )


@router.get("/{facility_id}")
async def get_facility(facility_id: str):
    try:
        return iris_client.get_facility(facility_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Facility not found") from exc


@router.delete("/{facility_id}", status_code=204)
async def delete_facility(facility_id: str):
    iris_client.delete_facility(facility_id)


@router.post("/{facility_id}/acquire")
async def trigger_acquisition(facility_id: str, background_tasks: BackgroundTasks):
    if facility_id not in iris_client.facilities:
        raise HTTPException(status_code=404, detail="Facility not found")
    model = iris_client.create_or_replace_model(facility_id, status="queued")
    background_tasks.add_task(acquire_images_for_facility, facility_id, iris_client.facilities[facility_id].address, model_id=model.model_id)
    return {"facility_id": facility_id, "status": model.status, "model_id": model.model_id}


@router.get("/{facility_id}/images")
async def list_facility_images(facility_id: str):
    """Return metadata for all imagery acquired for this facility."""
    images = iris_client.list_images_for_facility(facility_id)
    return [
        {
            "image_id": img.image_id,
            "url": img.public_url,
            "source": img.source,
            "category": img.category,
            "heading": img.heading,
            "content_type": img.content_type,
        }
        for img in images
    ]


@router.get("/{facility_id}/coverage")
async def get_coverage(facility_id: str):
    try:
        return iris_client.get_coverage(facility_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Coverage not found") from exc



async def _run_angle_generation(facility_id: str, facility_name: str, labels: list[str] | None) -> None:
    facility = iris_client.facilities.get(facility_id)
    if not facility:
        return
    images = await generate_multi_angle_views(facility_name, labels=labels)
    for img in images:
        label = img.get("label", "angle")
        key = f"facilities/{facility_id}/angles/{uuid4().hex[:8]}-fal-{label}.jpg"
        content_type = img.get("content_type", "image/jpeg")
        try:
            _store_fal_image(key, img["bytes"], content_type)
            public_url = _fal_public_url(key)
            iris_client.write_image_meta(
                ImageMeta(
                    image_id=f"img_{uuid4().hex[:8]}",
                    facility_id=facility_id,
                    source="supplemental_upload",
                    r2_key=key,
                    public_url=public_url,
                    category=label,
                    content_type=content_type,
                    created_at=facility.created_at,
                )
            )
        except Exception:
            pass


@router.get("/{facility_id}/angles")
async def list_angles(facility_id: str):
    """Return all fal.ai-generated angle images for this facility."""
    images = iris_client.list_images_for_facility(facility_id)
    return [
        {"label": img.category, "url": img.public_url}
        for img in images
        if img.category in _ANGLE_LABELS
    ]


@router.post("/{facility_id}/generate-angles")
async def generate_angles(
    facility_id: str,
    background_tasks: BackgroundTasks,
    labels: list[str] | None = None,
):
    """Kick off background fal.ai generation for multi-angle facility images."""
    try:
        facility = iris_client.get_facility(facility_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Facility not found") from exc

    background_tasks.add_task(_run_angle_generation, facility_id, facility["facility"].name, labels)
    return {"facility_id": facility_id, "status": "generating", "labels": labels}
