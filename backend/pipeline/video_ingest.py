from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.db.iris_client import iris_client
from backend.db.r2_client import r2_client
from backend.jobs.acquire_images import _fal_public_url, _image_key, _store_fal_image
from backend.models import ImageMeta, WorldModel
from backend.pipeline.classify import classify_image
from backend.pipeline.coverage import build_coverage_from_images
from backend.pipeline.scene_graph import extract_scene_graph
from backend.pipeline.spatial_bundle import build_spatial_bundle
from backend.pipeline.vr_video_extractor import extract_frames, extract_summary
from backend.pipeline.world_model import generate_world_model

UTC = timezone.utc


def _store_video_frame(key: str, payload: bytes, *, content_type: str) -> str:
    """
    Persist an extracted walkthrough frame and return a fetchable public URL.

    Uses R2 when configured, otherwise falls back to the same local asset path
    used by the fal.ai image helpers so local development remains functional.
    """
    _store_fal_image(key, payload, content_type)
    if r2_client.enabled:
        return r2_client.public_url_for(key)
    return _fal_public_url(key)


async def _extract_and_store_frames(
    facility_id: str,
    video_source: str | bytes,
    *,
    max_frames: int,
    equirect_crops: int,
) -> tuple[list[dict], dict]:
    frames = await asyncio.to_thread(
        extract_frames,
        video_source,
        max_frames=max_frames,
        equirect_crops=equirect_crops,
    )
    if not frames:
        raise RuntimeError("No usable frames extracted from video — video may be too dark, blurry, or corrupt")

    summary = extract_summary(frames)
    uploaded: list[dict] = []
    for index, frame in enumerate(frames, start=1):
        key = _image_key(facility_id, "vr_video", frame["file_name"])
        public_url = await asyncio.to_thread(
            _store_video_frame,
            key,
            frame["bytes"],
            content_type="image/jpeg",
        )
        meta = iris_client.write_image_meta(
            ImageMeta(
                image_id=f"img_{uuid4().hex[:8]}",
                facility_id=facility_id,
                source="vr_video",
                r2_key=key,
                public_url=public_url,
                heading=frame.get("heading"),
                content_type="image/jpeg",
                created_at=datetime.now(tz=UTC),
            )
        )
        uploaded.append(
            {
                **frame,
                "image_id": meta.image_id,
                "r2_key": meta.r2_key,
                "public_url": meta.public_url,
                "index": index,
            }
        )

    return uploaded, summary


async def _classify_frames(uploaded: list[dict]) -> list[dict]:
    classified = await asyncio.gather(
        *[
            classify_image(
                frame["bytes"],
                "vr_video",
                {"heading": frame.get("heading"), "index": frame["index"]},
            )
            for frame in uploaded
        ]
    )
    for image, classification in zip(uploaded, classified):
        iris_client.update_image_classification(
            image["image_id"],
            category=classification["category"],
            confidence=classification["confidence"],
            notes=classification["notes"],
        )
    return classified


async def ingest_video_source(
    facility_id: str,
    model_id: str,
    video_source: str | bytes,
    *,
    max_frames: int,
    equirect_crops: int,
    regenerate_world_model: bool = True,
) -> WorldModel:
    """
    Extract walkthrough frames, classify them, build a scene graph, and either:

    - generate a fresh world model and persist it to IRIS, or
    - refresh the analysis for an existing model while preserving its splat.
    """
    iris_client.update_model(model_id, status="acquiring", failure_reason="")
    facility = iris_client.facilities[facility_id]

    uploaded, summary = await _extract_and_store_frames(
        facility_id,
        video_source,
        max_frames=max_frames,
        equirect_crops=equirect_crops,
    )
    iris_client.update_model(model_id, status="classifying", source_image_count=summary["count"])

    classified = await _classify_frames(uploaded)

    covered, gaps = build_coverage_from_images(iris_client.list_images_for_facility(facility_id))
    iris_client.update_coverage(facility_id, covered, gaps)

    iris_client.update_model(model_id, status="generating")
    scene_graph = await extract_scene_graph(classified, {})
    spatial_bundle = build_spatial_bundle(scene_graph)

    if not regenerate_world_model:
        return iris_client.update_model(
            model_id,
            status="ready",
            scene_graph_json=scene_graph,
            source_image_count=summary["count"],
            spatial_bundle_json=spatial_bundle,
            completed_at=datetime.now(tz=UTC),
            failure_reason="",
        )

    world = await generate_world_model(
        uploaded,
        scene_graph,
        facility_id=facility_id,
        facility_name=facility.name,
    )
    return iris_client.write_world_model(facility_id, world, model_id=model_id)


async def ingest_video_file(
    facility_id: str,
    model_id: str,
    video_path: str,
    *,
    max_frames: int,
    equirect_crops: int,
    regenerate_world_model: bool = True,
) -> WorldModel:
    path = Path(video_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Video file not found: {path}")

    # Route local-file ingestion through the same bytes-based extraction path
    # as the HTTP upload endpoint. This avoids platform-specific codec issues
    # where OpenCV can fail to open the original container directly.
    video_bytes = await asyncio.to_thread(path.read_bytes)

    return await ingest_video_source(
        facility_id,
        model_id,
        video_bytes,
        max_frames=max_frames,
        equirect_crops=equirect_crops,
        regenerate_world_model=regenerate_world_model,
    )
