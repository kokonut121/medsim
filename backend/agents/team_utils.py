from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.agents.consensus import SEVERITY_SCORES


def make_finding(
    *,
    scan_id: str,
    domain: str,
    sub_agent: str,
    room_id: str,
    severity: str,
    confidence: float,
    label_text: str,
    recommendation: str,
    evidence_note: str,
    anchor: tuple[float, float, float],
) -> dict:
    return {
        "finding_id": f"finding_{uuid4().hex[:8]}",
        "scan_id": scan_id,
        "domain": domain,
        "sub_agent": sub_agent,
        "room_id": room_id,
        "severity": severity,
        "severity_score": SEVERITY_SCORES[severity],
        "compound_severity": SEVERITY_SCORES[severity],
        "label_text": label_text,
        "spatial_anchor": {"x": anchor[0], "y": anchor[1], "z": anchor[2]},
        "confidence": confidence,
        "evidence_r2_keys": [evidence_note],
        "recommendation": recommendation,
        "compound_domains": [domain],
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }

