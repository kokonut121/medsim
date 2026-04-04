from __future__ import annotations

from backend.agents.team_utils import make_finding


async def run(scan_id: str, world_model: dict) -> list[dict]:
    return [
        make_finding(
            scan_id=scan_id,
            domain="MSA",
            sub_agent="ADC-Inspector",
            room_id="MED-2",
            severity="ADVISORY",
            confidence=0.73,
            label_text="ADC in Med Room 2 faces active walkway with likely interruption exposure",
            recommendation="Reorient ADC away from traffic per ISMP medication safety workspace guidance",
            evidence_note="scene_graph:MED-2",
            anchor=(8.0, 1.0, 4.0),
        )
    ]

