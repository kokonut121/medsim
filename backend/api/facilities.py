from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.config import get_settings
from backend.db.iris_client import iris_client
from backend.jobs.acquire_images import acquire_images_for_facility
from backend.models import FacilityCreate
from backend.pipeline.facility_lookup import geocode_facility


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


@router.get("/{facility_id}/coverage")
async def get_coverage(facility_id: str):
    try:
        return iris_client.get_coverage(facility_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Coverage not found") from exc
