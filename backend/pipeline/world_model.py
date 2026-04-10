from __future__ import annotations

import asyncio
import json
import mimetypes
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from backend.config import get_settings
from backend.db.r2_client import r2_client


UTC = timezone.utc


def _pick_prompt_images(images: list[dict]) -> list[dict]:
    places = [image for image in images if image["source"] == "places"]
    street = [image for image in images if image["source"] == "street_view"]
    selected = (places[:4] or street[:4] or images[:4])[:4]
    return selected


def _world_prompt_from_images(images: list[dict], scene_graph: dict) -> dict:
    prompt_images = []
    for image in _pick_prompt_images(images):
        content = {"source": "uri", "uri": image["public_url"]}
        prompt_image = {"content": content}
        heading = image.get("heading")
        if heading is not None:
            prompt_image["azimuth"] = heading
        prompt_images.append(prompt_image)

    scene_summary = json.dumps(scene_graph)[:600]
    return {
        "type": "multi-image",
        "reconstruct_images": True,
        "multi_image_prompt": prompt_images,
        "text_prompt": f"Hospital trauma center environment reconstructed from public imagery. Scene context: {scene_summary}",
    }


async def _poll_world_completion(client: httpx.AsyncClient, operation_id: str, api_key: str, api_base: str) -> dict:
    deadline = datetime.now(tz=UTC) + timedelta(minutes=6)
    while datetime.now(tz=UTC) < deadline:
        response = await client.get(
            f"{api_base}/marble/v1/operations/{operation_id}",
            headers={"WLT-Api-Key": api_key},
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("done"):
            return payload
        await asyncio.sleep(3)
    raise RuntimeError("Timed out waiting for World Labs world generation")


def _extract_spz_url(world_payload: dict) -> tuple[str, str | None, str | None]:
    assets = world_payload.get("assets", {})
    splat_assets = assets.get("splats", {})
    spz_urls = splat_assets.get("spz_urls") or {}
    for candidate in ("full", "default", "high", "medium", "low"):
        if candidate in spz_urls:
            return spz_urls[candidate], assets.get("caption"), assets.get("imagery", {}).get("pano_url")
    if spz_urls:
        first_key = next(iter(spz_urls))
        return spz_urls[first_key], assets.get("caption"), assets.get("imagery", {}).get("pano_url")
    raise RuntimeError("World Labs response did not include a usable SPZ asset URL")


def _asset_extension(asset_url: str, content_type: str | None) -> str:
    parsed_path = urlparse(asset_url).path.lower()
    for extension in (".spz", ".ksplat", ".splat", ".ply"):
        if parsed_path.endswith(extension):
            return extension

    guessed = mimetypes.guess_extension(content_type or "application/octet-stream")
    if guessed and guessed != ".bin":
        return guessed
    return ".spz"


async def generate_world_model(images: list[dict], scene_graph: dict, *, facility_id: str, facility_name: str) -> dict:
    settings = get_settings()

    if settings.use_synthetic_fallbacks or not settings.world_labs_api_key:
        digest = str(abs(hash(tuple(image["public_url"] for image in images))))[:12]
        return {
            "world_id": f"world_{digest}",
            "splat_url": f"worlds/{digest}/scene.spz",
            "scene_manifest": scene_graph,
            "source_image_count": len(images),
            "caption": "Synthetic world-model fallback",
        }

    api_base = settings.world_labs_api_base.rstrip("/")
    request_payload = {
        "display_name": f"{facility_name} world model",
        "world_prompt": _world_prompt_from_images(images, scene_graph),
    }
    async with httpx.AsyncClient(timeout=120) as client:
        start = await client.post(
            f"{api_base}/marble/v1/worlds:generate",
            headers={
                "Content-Type": "application/json",
                "WLT-Api-Key": settings.world_labs_api_key,
            },
            json=request_payload,
        )
        # Graceful fallback on payment/quota errors
        if start.status_code in (402, 429, 403):
            digest = str(abs(hash(tuple(img.get("public_url", "") for img in images))))[:12]
            return {
                "world_id": f"world_{digest}",
                "splat_url": f"worlds/{digest}/scene.spz",
                "scene_manifest": scene_graph,
                "source_image_count": len(images),
                "caption": f"World Labs quota exceeded — synthetic fallback (real images acquired: {len(images)})",
                "world_marble_url": None,
            }
        start.raise_for_status()
        operation = start.json()
        operation_id = operation["operation_id"]
        completed = await _poll_world_completion(client, operation_id, settings.world_labs_api_key, api_base)
        if completed.get("error"):
            message = completed["error"].get("message", "World Labs generation failed")
            raise RuntimeError(message)

        world = completed.get("response") or {}
        world_id = world.get("world_id") or operation_id
        spz_url, caption, thumbnail_url = _extract_spz_url(world)
        asset_response = await client.get(spz_url)
        asset_response.raise_for_status()

    extension = _asset_extension(spz_url, asset_response.headers.get("content-type"))
    key = f"facilities/{facility_id}/models/{world_id}/scene{extension}"
    r2_client.upload_bytes(key, asset_response.content, content_type=asset_response.headers.get("content-type", "application/octet-stream"))
    return {
        "world_id": world_id,
        "splat_url": key,
        "scene_manifest": scene_graph,
        "source_image_count": len(images),
        "caption": caption,
        "thumbnail_url": thumbnail_url,
        "world_marble_url": world.get("world_marble_url"),
    }
