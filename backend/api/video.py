from __future__ import annotations

"""
VR / 360-degree video upload and frame-extraction endpoint.

POST /api/video/extract/{facility_id}
  Accepts a raw video file (multipart or raw body).
  Extracts high-quality frames, uploads them to R2, classifies them,
  and queues world-model generation — same as the acquire pipeline but
  seeded from a local video rather than Google imagery.

The endpoint is non-blocking: it enqueues a background task and returns
immediately with a model_id the client can poll via
  GET /api/models/{unit_id}/status
"""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile

from backend.db.iris_client import iris_client
from backend.db.r2_client import r2_client
from backend.jobs.acquire_images import _fal_public_url, _image_key, _store_fal_image
from backend.models import ImageMeta
from backend.pipeline.classify import classify_image
from backend.pipeline.coverage import build_coverage_from_images
from backend.pipeline.scene_graph import extract_scene_graph
from backend.pipeline.vr_video_extractor import extract_frames, extract_summary
from backend.pipeline.world_model import generate_world_model

router = APIRouter(prefix="/api/video", tags=["video"])
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


async def _process_video(
    facility_id: str,
    model_id: str,
    video_bytes: bytes,
    max_frames: int,
    equirect_crops: int,
) -> None:
    """Background task: extract → classify → scene graph → world model."""
    try:
        iris_client.update_model(model_id, status="acquiring", failure_reason="")
        facility = iris_client.facilities[facility_id]

        # 1. Extract frames from video
        frames = await asyncio.to_thread(
            extract_frames,
            video_bytes,
            max_frames=max_frames,
            equirect_crops=equirect_crops,
        )
        if not frames:
            raise RuntimeError("No usable frames extracted from video — video may be too dark, blurry, or corrupt")

        summary = extract_summary(frames)
        iris_client.update_model(model_id, status="classifying", source_image_count=summary["count"])

        # 2. Persist extracted frames + store ImageMeta
        uploaded: list[dict] = []
        for i, frame in enumerate(frames, start=1):
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
            uploaded.append({**frame, "image_id": meta.image_id, "r2_key": meta.r2_key,
                              "public_url": meta.public_url, "index": i})

        # 3. Classify all frames in parallel
        classified = await asyncio.gather(
            *[classify_image(f["bytes"], "vr_video", {"heading": f.get("heading"), "index": f["index"]})
              for f in uploaded]
        )
        for img, cls in zip(uploaded, classified):
            iris_client.update_image_classification(
                img["image_id"],
                category=cls["category"],
                confidence=cls["confidence"],
                notes=cls["notes"],
            )

        # 4. Coverage map
        covered, gaps = build_coverage_from_images(iris_client.list_images_for_facility(facility_id))
        iris_client.update_coverage(facility_id, covered, gaps)

        # 5. Scene graph
        iris_client.update_model(model_id, status="generating")
        scene_graph = await extract_scene_graph(classified, {})

        # 6. World model
        world = await generate_world_model(
            uploaded, scene_graph,
            facility_id=facility_id,
            facility_name=facility.name,
        )
        iris_client.write_world_model(facility_id, world, model_id=model_id)

    except Exception as exc:
        iris_client.update_model(model_id, status="failed", failure_reason=str(exc))
        raise


@router.post("/extract/{facility_id}")
async def extract_video(
    facility_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    max_frames: int = Query(default=20, ge=4, le=60,
                            description="Max frames to extract (after 360° cropping)"),
    equirect_crops: int = Query(default=6, ge=0, le=12,
                                description="360° horizontal crop windows per frame (0=disable)"),
):
    """
    Upload a VR/360 video and kick off world-model generation.

    - Accepts any video format OpenCV can decode (mp4, mov, avi, webm, mkv).
    - For equirectangular (2:1 ratio) videos, splits each frame into
      `equirect_crops` perspective windows covering 360°.
    - Returns immediately; poll GET /api/models/{unit_id}/status for progress.
    """
    if facility_id not in iris_client.facilities:
        raise HTTPException(status_code=404, detail="Facility not found")

    content_type = file.content_type or ""
    if content_type and not content_type.startswith("video/") and not content_type == "application/octet-stream":
        raise HTTPException(
            status_code=415,
            detail=f"Expected a video file, got content-type: {content_type}",
        )

    video_bytes = await file.read()
    if len(video_bytes) < 1024:
        raise HTTPException(status_code=400, detail="File too small to be a valid video")

    model = iris_client.create_or_replace_model(facility_id, status="queued")
    background_tasks.add_task(
        _process_video,
        facility_id,
        model.model_id,
        video_bytes,
        max_frames,
        equirect_crops,
    )

    return {
        "facility_id": facility_id,
        "model_id": model.model_id,
        "status": "queued",
        "file_name": file.filename,
        "file_size_mb": round(len(video_bytes) / 1_048_576, 2),
        "max_frames": max_frames,
        "equirect_crops": equirect_crops,
        "poll_url": f"/api/models/{next(u.unit_id for u in iris_client.units.values() if u.facility_id == facility_id)}/status",
    }
