from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.db.iris_client import iris_client, latest_complete_scan_or_latest
from backend.reports.pdf_generator import build_pdf


router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{unit_id}/pdf")
async def get_pdf(unit_id: str):
    scans = [scan for scan in iris_client.scans.values() if scan.unit_id == unit_id]
    scan = latest_complete_scan_or_latest(scans)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    pdf_bytes = build_pdf(scan)
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/{unit_id}/manifest")
async def get_manifest(unit_id: str):
    scans = [scan for scan in iris_client.scans.values() if scan.unit_id == unit_id]
    scan = latest_complete_scan_or_latest(scans)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {"scan_id": scan.scan_id, "findings": [finding.model_dump(mode="json") for finding in scan.findings]}
