from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.facilities import router as facilities_router
from backend.api.fhir import router as fhir_router
from backend.api.models import router as models_router
from backend.api.reports import router as reports_router
from backend.api.scans import router as scans_router
from backend.api.upload import router as upload_router
from backend.api.websocket import router as websocket_router
from backend.config import get_settings


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
app.include_router(scans_router)
app.include_router(upload_router)
app.include_router(fhir_router)
app.include_router(reports_router)
app.include_router(websocket_router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}

