"""Infection Control & Asepsis — hand hygiene dispenser presence and accessibility."""
from __future__ import annotations

from backend.agents.team_utils import accessible_equipment, has_equipment, make_finding, rooms_from_model

_SKIP = {"building_exterior", "utility_support"}


async def run(scan_id: str, world_model: dict) -> list[dict]:
    findings: list[dict] = []
    for room in rooms_from_model(world_model):
        if room.get("type") in _SKIP:
            continue
        if not has_equipment(room, "hand_hygiene_dispenser"):
            # Pin at the door entry of the room — where the dispenser should be
            findings.append(make_finding(
                scan_id=scan_id, domain="ICA", sub_agent="HAI-Scout", room=room,
                severity="HIGH", confidence=0.92,
                label_text=f"No hand hygiene dispenser at {room['room_id']} entry",
                recommendation="Install ABHR dispenser at room entry per CDC Hand Hygiene Guideline §IV.C",
                eq_type="hand_hygiene_dispenser",   # snaps to door-entry position
            ))
        elif not accessible_equipment(room, "hand_hygiene_dispenser"):
            findings.append(make_finding(
                scan_id=scan_id, domain="ICA", sub_agent="HAI-Scout", room=room,
                severity="ADVISORY", confidence=0.78,
                label_text=f"Dispenser in {room['room_id']} obstructed or low-stock",
                recommendation="Clear obstruction or mount second dispenser per TJC IC.02.01.01 EP 2",
                eq_type="hand_hygiene_dispenser",
            ))
    return findings
