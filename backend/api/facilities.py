from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.db.iris_client import iris_client
from backend.jobs.acquire_images import acquire_images_for_facility
from backend.models import FacilityCreate


router = APIRouter(prefix="/api/facilities", tags=["facilities"])


@router.get("")
async def list_facilities():
    return iris_client.list_facilities()


@router.post("")
async def create_facility(payload: FacilityCreate):
    return iris_client.create_facility(payload)


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
async def trigger_acquisition(facility_id: str):
    if facility_id not in iris_client.facilities:
        raise HTTPException(status_code=404, detail="Facility not found")
    return await acquire_images_for_facility(facility_id, iris_client.facilities[facility_id].address)


@router.get("/{facility_id}/coverage")
async def get_coverage(facility_id: str):
    try:
        return iris_client.get_coverage(facility_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Coverage not found") from exc
