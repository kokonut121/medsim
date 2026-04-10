from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.db.iris_client import iris_client


router = APIRouter(prefix="/api/fhir", tags=["fhir"])


@router.get("/DiagnosticReport/{scan_id}")
async def get_diagnostic_report(scan_id: str):
    try:
        return iris_client.get_diagnostic_report_resource(scan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Scan not found")
    except Exception as exc:
        raise HTTPException(status_code=502, detail="FHIR repository request failed") from exc


@router.get("/Observation/{finding_id}")
async def get_observation(finding_id: str):
    try:
        return iris_client.get_observation_resource(finding_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Finding not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="FHIR repository request failed") from exc


@router.post("/DiagnosticReport/$push")
async def push_diagnostic_report(payload: dict):
    scan_id = payload.get("scan_id")
    if not scan_id:
        raise HTTPException(status_code=400, detail="scan_id is required")
    try:
        return iris_client.push_diagnostic_report(scan_id, payload.get("target"))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Scan not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="FHIR push failed") from exc
