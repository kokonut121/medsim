from __future__ import annotations

from backend.agents.team_utils import make_finding


async def run(scan_id: str, world_model: dict) -> list[dict]:
    return [
        make_finding(
            scan_id=scan_id,
            domain="ICA",
            sub_agent="HAI-Scout",
            room_id="R101",
            severity="HIGH",
            confidence=0.86,
            label_text="No hand hygiene dispenser within 3 ft of Room R101 entry threshold",
            recommendation="Relocate dispenser to room entry per CDC Hand Hygiene Guideline 2002 Section IV.C",
            evidence_note="scene_graph:R101",
            anchor=(3.0, 1.0, 2.5),
        )
    ]

