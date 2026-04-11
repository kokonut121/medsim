from __future__ import annotations

import asyncio
import logging
import pathlib

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.api.facilities import router as facilities_router
from backend.api.fhir import router as fhir_router
from backend.api.models import router as models_router
from backend.api.optimize import router as optimize_router
from backend.api.reports import router as reports_router
from backend.api.scans import router as scans_router
from backend.api.simulate import router as simulate_router
from backend.api.upload import router as upload_router
from backend.api.video import router as video_router
from backend.api.websocket import router as websocket_router
from backend.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facilities_router)
app.include_router(models_router)
app.include_router(optimize_router)
app.include_router(scans_router)
app.include_router(simulate_router)
app.include_router(upload_router)
app.include_router(video_router)
app.include_router(fhir_router)
app.include_router(reports_router)
app.include_router(websocket_router)


@app.on_event("shutdown")
async def _close_redis() -> None:
    from backend.db.redis_client import redis_client

    await redis_client.close()


@app.on_event("startup")
async def _auto_scan_on_startup() -> None:
    """Run an initial safety scan for every ready model so findings are populated immediately."""
    from backend.agents.orchestrator import run_scan
    from backend.db.iris_client import iris_client

    async def _scan(unit_id: str, model_id: str) -> None:
        try:
            await run_scan(unit_id, model_id)
            logger.info("Startup scan complete for %s", unit_id)
        except Exception as exc:
            logger.warning("Startup scan failed for %s: %s", unit_id, exc)

    tasks = [
        _scan(m.unit_id, m.model_id)
        for m in iris_client.models.values()
        if m.status == "ready"
    ]
    if tasks:
        await asyncio.gather(*tasks)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}


_FAL_DIR = pathlib.Path("data/fal_images")


@app.get("/api/fal-images/{filename:path}")
async def serve_fal_image(filename: str):
    """Serve locally-stored fal.ai generated images when R2 is not configured."""
    path = _FAL_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    suffix = path.suffix.lower()
    media = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
    return FileResponse(path, media_type=media, headers={"Cache-Control": "public, max-age=86400"})

