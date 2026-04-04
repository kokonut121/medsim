from __future__ import annotations

from backend.agents.team_utils import make_finding


async def run(scan_id: str, world_model: dict) -> list[dict]:
    return [
        make_finding(
            scan_id=scan_id,
            domain="SCA",
            sub_agent="Handoff-Zone-Auditor",
            room_id="NS-1",
            severity="HIGH",
            confidence=0.82,
            label_text="Primary handoff zone lacks acoustic separation for high-risk care transitions",
            recommendation="Create enclosed handoff space per TJC communication safety recommendations",
            evidence_note="scene_graph:NS-1",
            anchor=(18.0, 1.0, 11.0),
        )
    ]

