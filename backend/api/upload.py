from __future__ import annotations

import base64
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request, Response

from backend.db.iris_client import iris_client
from backend.db.r2_client import r2_client
from backend.jobs.acquire_images import _image_key
from backend.models import ImageMeta
from backend.pipeline.classify import classify_image
from backend.pipeline.coverage import build_coverage_from_images


router = APIRouter(prefix="/api/upload/supplemental", tags=["upload"])
UTC = timezone.utc


def _parse_upload_metadata(raw_metadata: str | None) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not raw_metadata:
        return parsed
    for part in raw_metadata.split(","):
        if " " not in part:
            continue
        key, encoded = part.strip().split(" ", 1)
        parsed[key] = base64.b64decode(encoded).decode("utf-8")
    return parsed


@router.post("")
async def create_upload(
    request: Request,
    response: Response,
    upload_length: int = Header(default=0, alias="Upload-Length"),
    upload_metadata: str | None = Header(default=None, alias="Upload-Metadata"),
):
    metadata = _parse_upload_metadata(upload_metadata)
    facility_id = metadata.get("facility_id")
    if not facility_id or facility_id not in iris_client.facilities:
        raise HTTPException(status_code=400, detail="facility_id metadata is required for supplemental uploads")

    upload_id = f"upload_{uuid4().hex[:8]}"
    iris_client.create_upload_session(
        upload_id,
        {
            "facility_id": facility_id,
            "upload_length": upload_length,
            "offset": 0,
            "buffer": b"",
            "metadata": metadata,
            "content_type": metadata.get("filetype", request.headers.get("content-type", "image/jpeg")),
        },
    )
    response.status_code = 201
    response.headers["Location"] = f"/api/upload/supplemental/{upload_id}"
    response.headers["Tus-Resumable"] = "1.0.0"
    response.headers["Upload-Offset"] = "0"
    return {"upload_id": upload_id, "upload_length": upload_length}


@router.head("/{upload_id}")
async def head_upload(upload_id: str, response: Response):
    try:
        session = iris_client.get_upload_session(upload_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Upload not found") from exc
    response.headers["Tus-Resumable"] = "1.0.0"
    response.headers["Upload-Offset"] = str(session["offset"])
    response.headers["Upload-Length"] = str(session["upload_length"])
    return Response(status_code=200, headers=response.headers)


@router.patch("/{upload_id}")
async def patch_upload(
    upload_id: str,
    request: Request,
    response: Response,
    upload_offset: int = Header(default=0, alias="Upload-Offset"),
):
    try:
        session = iris_client.get_upload_session(upload_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Upload not found") from exc

    if upload_offset != session["offset"]:
        raise HTTPException(status_code=409, detail="Upload offset mismatch")

    chunk = await request.body()
    buffer = session["buffer"] + chunk
    new_offset = upload_offset + len(chunk)
    iris_client.update_upload_session(upload_id, buffer=buffer, offset=new_offset)

    if new_offset >= session["upload_length"]:
        metadata = session["metadata"]
        file_name = metadata.get("filename", f"{upload_id}.jpg")
        facility_id = session["facility_id"]
        key = _image_key(facility_id, "supplemental_upload", file_name)
        r2_client.upload_bytes(key, buffer, content_type=session["content_type"])
        image_meta = iris_client.write_image_meta(
            ImageMeta(
                image_id=f"img_{uuid4().hex[:8]}",
                facility_id=facility_id,
                source="supplemental_upload",
                r2_key=key,
                public_url=r2_client.public_url_for(key),
                content_type=session["content_type"],
                created_at=datetime.now(tz=UTC),
            )
        )
        classification = await classify_image(buffer, "supplemental_upload")
        iris_client.update_image_classification(
            image_meta.image_id,
            category=classification["category"],
            confidence=classification["confidence"],
            notes=classification["notes"],
        )
        covered_areas, gap_areas = build_coverage_from_images(iris_client.list_images_for_facility(facility_id))
        iris_client.update_coverage(facility_id, covered_areas, gap_areas)

    response.status_code = 204
    response.headers["Tus-Resumable"] = "1.0.0"
    response.headers["Upload-Offset"] = str(new_offset)
    return Response(status_code=204, headers=response.headers)
