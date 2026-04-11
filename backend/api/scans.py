from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from backend.agents.orchestrator import create_scan, run_scan_background
from backend.db.iris_client import iris_client
from backend.models import Scan

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.post("/{unit_id}/run")
async def trigger_scan(unit_id: str, background_tasks: BackgroundTasks) -> dict:
    """
    Start a background scan. Returns immediately with queued envelope.
    Subscribe to WS /ws/scans/{unit_id}/live for live domain_status / finding / complete events.
    """
    try:
        model = iris_client.get_model(unit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="World model not found") from exc
    if model.status != "ready":
        raise HTTPException(status_code=409, detail=f"Model is {model.status}, not ready")

    scan = create_scan(unit_id)
    background_tasks.add_task(run_scan_background, unit_id, scan.scan_id)

    return {
        "scan_id": scan.scan_id,
        "unit_id": unit_id,
        "status": "queued",
        "domain_statuses": {d: s.model_dump() for d, s in scan.domain_statuses.items()},
        "triggered_at": scan.triggered_at.isoformat(),
    }


@router.get("/{unit_id}/status")
async def get_scan_status(unit_id: str):
    scans = [s for s in iris_client.scans.values() if s.unit_id == unit_id]
    if not scans:
        raise HTTPException(status_code=404, detail="No scans for unit")
    return sorted(scans, key=lambda s: s.triggered_at)[-1]


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
