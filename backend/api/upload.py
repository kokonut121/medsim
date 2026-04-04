from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Header, Response


router = APIRouter(prefix="/api/upload/supplemental", tags=["upload"])


@router.post("")
async def create_upload(response: Response, upload_length: int = Header(default=0, alias="Upload-Length")):
    upload_id = f"upload_{uuid4().hex[:8]}"
    response.headers["Location"] = f"/api/upload/supplemental/{upload_id}"
    response.headers["Tus-Resumable"] = "1.0.0"
    return {"upload_id": upload_id, "upload_length": upload_length}


@router.patch("/{upload_id}")
async def patch_upload(upload_id: str, response: Response):
    response.headers["Tus-Resumable"] = "1.0.0"
    response.headers["Upload-Offset"] = "0"
    return {"upload_id": upload_id, "status": "received"}

