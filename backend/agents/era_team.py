"""Emergency Response Adequacy — crash cart coverage and call light presence."""
from __future__ import annotations

from backend.agents.team_utils import accessible_equipment, has_equipment, make_finding, rooms_from_model

_PATIENT = {"patient_room", "icu_bay", "operating_room"}


async def run(scan_id: str, world_model: dict) -> list[dict]:
    findings: list[dict] = []
    rooms = rooms_from_model(world_model)
    patient_rooms = [r for r in rooms if r.get("type") in _PATIENT]
    has_any_cart = any(has_equipment(r, "crash_cart") for r in rooms)

    for room in patient_rooms:
        if not has_equipment(room, "call_light"):
            findings.append(make_finding(
                scan_id=scan_id, domain="ERA", sub_agent="CrashCart-Mapper", room=room,
                severity="HIGH", confidence=0.88,
                label_text=f"Call light absent from {room['room_id']}",
                recommendation="Install bed-rail call light per CMS CoP §482.13(e)",
                eq_type="call_light",   # pins at bed-rail position
            ))
        if not has_any_cart:
            findings.append(make_finding(
                scan_id=scan_id, domain="ERA", sub_agent="CrashCart-Mapper", room=room,
                severity="CRITICAL", confidence=0.95,
                label_text=f"No crash cart near {room['room_id']}",
                recommendation="Stage crash cart in adjacent corridor per AHA ACLS placement guidance",
                eq_type="crash_cart",
            ))
        elif has_equipment(room, "crash_cart") and not accessible_equipment(room, "crash_cart"):
            findings.append(make_finding(
                scan_id=scan_id, domain="ERA", sub_agent="CrashCart-Mapper", room=room,
                severity="CRITICAL", confidence=0.91,
                label_text=f"Crash cart in {room['room_id']} is blocked",
                recommendation="Clear 3 ft around crash cart per AHA ACLS 60-second response standard",
                eq_type="crash_cart",
            ))
    return findings
