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

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile

from backend.db.iris_client import iris_client
from backend.pipeline.video_ingest import ingest_video_source

router = APIRouter(prefix="/api/video", tags=["video"])


async def _process_video(
    facility_id: str,
    model_id: str,
    video_bytes: bytes,
    max_frames: int,
    equirect_crops: int,
) -> None:
    """Background task: extract → classify → scene graph → world model."""
    try:
        await ingest_video_source(
            facility_id,
            model_id,
            video_bytes,
            max_frames=max_frames,
            equirect_crops=equirect_crops,
        )
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
