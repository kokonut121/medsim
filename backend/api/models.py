from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.config import get_settings
from backend.db.iris_client import iris_client


router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/{unit_id}/status")
async def get_status(unit_id: str):
    try:
        model = iris_client.get_model(unit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model not found") from exc
    return {
        "unit_id": unit_id,
        "model_id": model.model_id,
        "status": model.status,
        "failure_reason": model.failure_reason,
        "source_image_count": model.source_image_count,
        "caption": model.caption,
        "thumbnail_url": model.thumbnail_url,
        "world_marble_url": model.world_marble_url,
        "completed_at": model.completed_at,
    }


@router.get("/{unit_id}/splat")
async def get_splat(unit_id: str):
    settings = get_settings()
    model = iris_client.get_model(unit_id)
    if model.status != "ready":
        raise HTTPException(status_code=409, detail=f"Model is {model.status}")
    if not model.splat_r2_key:
        raise HTTPException(status_code=404, detail="Model asset not found")
    return {"unit_id": unit_id, "signed_url": f"{settings.r2_public_url}/{model.splat_r2_key}"}


@router.get("/{unit_id}/scene_graph")
async def get_scene_graph(unit_id: str):
    return iris_client.get_model(unit_id).scene_graph_json
