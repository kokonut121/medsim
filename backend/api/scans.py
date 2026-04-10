from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.agents.orchestrator import run_scan
from backend.db.iris_client import iris_client


router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.post("/{unit_id}/run")
async def trigger_scan(unit_id: str):
    model = iris_client.get_model(unit_id)
    if model.status != "ready":
        raise HTTPException(status_code=409, detail=f"Model is {model.status}")
    return await run_scan(unit_id, model.model_id)


@router.get("/{unit_id}/status")
async def get_scan_status(unit_id: str):
    scans = [scan for scan in iris_client.scans.values() if scan.unit_id == unit_id]
    if not scans:
        raise HTTPException(status_code=404, detail="Scan not found")
    return sorted(scans, key=lambda scan: scan.triggered_at)[-1]


@router.get("/{unit_id}/findings")
async def get_findings(
    unit_id: str,
    domain: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    room_id: str | None = Query(default=None),
):
    return iris_client.list_findings(unit_id, domain=domain, severity=severity, room_id=room_id)


@router.get("/{unit_id}/findings/{finding_id}")
async def get_finding(unit_id: str, finding_id: str):
    try:
        finding = iris_client.get_finding(finding_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Finding not found") from exc
    if finding.scan_id not in iris_client.scans:
        raise HTTPException(status_code=404, detail="Scan not found")
    return finding
