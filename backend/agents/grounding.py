"""
Grounding & validation pass
============================
Takes raw LLM-emitted finding candidates and:
  - rejects unknown room_id or equipment_ref references
  - snaps spatial_anchor to bundle anchor coordinates
  - enforces schema bounds (severity enum, confidence [0,1])
  - drops candidates missing required text fields
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

_SEVERITY_VALID = {"CRITICAL", "HIGH", "ADVISORY"}
_SEVERITY_SCORES = {"CRITICAL": 1.0, "HIGH": 0.7, "ADVISORY": 0.4}


def ground_candidates(
    candidates: list[dict],
    bundle: dict,
    scan_id: str,
) -> list[dict]:
    """
    Validate and ground a list of raw LLM candidates against the spatial bundle.
    Returns only passing candidates with anchors snapped to bundle coordinates.
    """
    room_index: dict[str, dict] = bundle.get("room_index", {})
    grounded: list[dict] = []

    for c in candidates:
        room_id = (c.get("room_id") or "").strip()
        if not room_id or room_id not in room_index:
            continue  # unknown room — reject

        room = room_index[room_id]
        eq_ref = (c.get("equipment_ref") or "").strip() or None

        # Snap spatial anchor to bundle anchor
        if eq_ref:
            eq_list = room.get("equipment", [])
            eq_match = next((e for e in eq_list if e.get("type") == eq_ref), None)
            anchor = eq_match["anchor"] if eq_match else room["center"]
        else:
            anchor = room["center"]

        # Severity enforcement
        severity = (c.get("severity") or "ADVISORY").upper()
        if severity not in _SEVERITY_VALID:
            severity = "ADVISORY"

        # Confidence bounds
        try:
            confidence = float(c.get("confidence", 0.7))
        except (TypeError, ValueError):
            confidence = 0.7
        confidence = max(0.0, min(1.0, confidence))

        # Require non-empty text fields
        label = (c.get("label_text") or "").strip()
        recommendation = (c.get("recommendation") or "").strip()
        if not label or not recommendation:
            continue

        # Truncate to safe lengths
        label = label[:120]
        recommendation = recommendation[:200]

        grounded.append({
            "finding_id": f"finding_{uuid.uuid4().hex[:8]}",
            "scan_id": scan_id,
            "domain": (c.get("domain") or "ICA").upper(),
            "sub_agent": (c.get("sub_agent") or "auditor"),
            "room_id": room_id,
            "severity": severity,
            "severity_score": _SEVERITY_SCORES[severity],
            "compound_severity": _SEVERITY_SCORES[severity],
            "label_text": label,
            "spatial_anchor": anchor,
            "confidence": round(confidence, 3),
            "evidence_r2_keys": [f"bundle:{room_id}:{eq_ref or 'room'}"],
            "recommendation": recommendation,
            "compound_domains": [(c.get("domain") or "ICA").upper()],
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        })

    return grounded
