from __future__ import annotations

import boto3
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

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
    if settings.use_synthetic_fallbacks or not settings.r2_account_id:
        if model.world_marble_url:
            return {"unit_id": unit_id, "signed_url": model.world_marble_url}
        raise HTTPException(status_code=404, detail="No splat asset available")
    if not model.splat_r2_key:
        raise HTTPException(status_code=404, detail="Model asset not found")
    # Return both the public R2 URL and a CORS-safe proxy URL
    public_url = f"{settings.r2_public_url}/{model.splat_r2_key}"
    return {
        "unit_id": unit_id,
        "signed_url": public_url,
        "stream_url": f"/api/models/{unit_id}/splat/stream",
    }


@router.get("/{unit_id}/splat/stream")
async def stream_splat(unit_id: str):
    """
    Proxy the .spz asset from R2 directly through the backend.
    Adds Access-Control-Allow-Origin: * so the browser can fetch it
    without hitting R2's missing CORS config.
    """
    settings = get_settings()
    model = iris_client.get_model(unit_id)
    if model.status != "ready":
        raise HTTPException(status_code=409, detail=f"Model is {model.status}")
    if not model.splat_r2_key:
        raise HTTPException(status_code=404, detail="Model asset not found")

    if settings.use_synthetic_fallbacks or not settings.r2_account_id:
        raise HTTPException(status_code=404, detail="R2 not configured — no splat asset available")

    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )

    try:
        obj = s3.get_object(Bucket=settings.r2_bucket_name, Key=model.splat_r2_key)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"R2 fetch failed: {exc}") from exc

    content_type = obj.get("ContentType", "application/octet-stream")
    body = obj["Body"]

    def _iter():
        while chunk := body.read(65536):
            yield chunk

    return StreamingResponse(
        _iter(),
        media_type=content_type,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD",
            "Cache-Control": "public, max-age=86400",
            "Content-Length": str(obj.get("ContentLength", "")),
        },
    )


@router.get("/{unit_id}/scene_graph")
async def get_scene_graph(unit_id: str):
    return iris_client.get_model(unit_id).scene_graph_json
