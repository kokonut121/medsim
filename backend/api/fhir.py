from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.db.iris_client import iris_client
from backend.reports.fhir_projector import build_diagnostic_report, build_observation


router = APIRouter(prefix="/api/fhir", tags=["fhir"])


@router.get("/DiagnosticReport/{scan_id}")
async def get_diagnostic_report(scan_id: str):
    scan = iris_client.scans.get(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return build_diagnostic_report(scan)


@router.get("/Observation/{finding_id}")
async def get_observation(finding_id: str):
    try:
        finding = iris_client.get_finding(finding_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Finding not found") from exc
    return build_observation(finding)


@router.post("/DiagnosticReport/$push")
async def push_diagnostic_report(payload: dict):
    return {"status": "queued", "target": payload.get("target"), "scan_id": payload.get("scan_id")}

