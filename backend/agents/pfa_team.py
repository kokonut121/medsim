from __future__ import annotations

from backend.agents.team_utils import make_finding


async def run(scan_id: str, world_model: dict) -> list[dict]:
    return [
        make_finding(
            scan_id=scan_id,
            domain="PFA",
            sub_agent="Discharge-Pathfinder",
            room_id="D-1",
            severity="ADVISORY",
            confidence=0.71,
            label_text="Discharge corridor bottleneck near elevator lobby may delay bed turnover",
            recommendation="Clear staging items from discharge path per ACEP throughput best practices",
            evidence_note="scene_graph:D-1",
            anchor=(15.0, 1.0, 9.0),
        )
    ]

