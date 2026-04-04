from __future__ import annotations

from backend.models import Finding, Scan


def build_diagnostic_report(scan: Scan) -> dict:
    return {
        "resourceType": "DiagnosticReport",
        "id": scan.scan_id,
        "status": "final",
        "code": {"text": f"MedSentinel Scan {scan.scan_id}"},
        "conclusion": f"{len(scan.findings)} findings synthesized for unit {scan.unit_id}",
        "result": [{"reference": f"Observation/{finding.finding_id}"} for finding in scan.findings],
    }


def build_observation(finding: Finding) -> dict:
    return {
        "resourceType": "Observation",
        "id": finding.finding_id,
        "status": "final",
        "code": {"text": f"{finding.domain} finding"},
        "valueString": finding.label_text,
        "note": [{"text": finding.recommendation}],
    }

