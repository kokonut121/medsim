from __future__ import annotations

from backend.agents.team_utils import make_finding


async def run(scan_id: str, world_model: dict) -> list[dict]:
    return [
        make_finding(
            scan_id=scan_id,
            domain="ERA",
            sub_agent="CrashCart-Mapper",
            room_id="R104",
            severity="CRITICAL",
            confidence=0.91,
            label_text="Crash cart coverage to Room R104 exceeds 60-second code response threshold",
            recommendation="Move crash cart to central corridor per AHA ACLS cart placement guidance",
            evidence_note="scene_graph:R104",
            anchor=(4.8, 1.2, 2.7),
        )
    ]

