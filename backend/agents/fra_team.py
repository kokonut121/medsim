from __future__ import annotations

from backend.agents.team_utils import make_finding


async def run(scan_id: str, world_model: dict) -> list[dict]:
    return [
        make_finding(
            scan_id=scan_id,
            domain="FRA",
            sub_agent="Room-Geometer",
            room_id="R103",
            severity="HIGH",
            confidence=0.8,
            label_text="Bedside clearance at Room R103 appears below 36-inch fall recovery minimum",
            recommendation="Increase bedside clearance to ANSI 36-inch minimum for assistive transfer access",
            evidence_note="scene_graph:R103",
            anchor=(12.0, 0.8, 5.0),
        )
    ]

