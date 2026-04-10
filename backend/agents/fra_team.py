"""Fall Risk Assessment — sightlines, IV pole access, call light."""
from __future__ import annotations

from backend.agents.team_utils import accessible_equipment, has_equipment, make_finding, room_center_pos, rooms_from_model

_PATIENT = {"patient_room", "icu_bay"}


async def run(scan_id: str, world_model: dict) -> list[dict]:
    findings: list[dict] = []
    for room in rooms_from_model(world_model):
        if room.get("type") not in _PATIENT:
            continue
        if not room.get("sightline_to_nursing_station", True):
            findings.append(make_finding(
                scan_id=scan_id, domain="FRA", sub_agent="Room-Geometer", room=room,
                severity="HIGH", confidence=0.84,
                # Pin at room centre — the whole room is the issue
                label_text=f"{room['room_id']} has no sightline to nursing station",
                recommendation="Install glass partition or camera feed per ANSI/HFES 200.2",
            ))
        if has_equipment(room, "iv_pole") and not accessible_equipment(room, "iv_pole"):
            findings.append(make_finding(
                scan_id=scan_id, domain="FRA", sub_agent="Room-Geometer", room=room,
                severity="ADVISORY", confidence=0.76,
                label_text=f"IV pole in {room['room_id']} obstructed — fall risk during ambulation",
                recommendation="Ensure 36-inch clear path around IV pole per ANSI A117.1",
                eq_type="iv_pole",   # pins on the actual iv pole position
            ))
    return findings
