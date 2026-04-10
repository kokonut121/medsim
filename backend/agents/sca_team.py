"""Safe Communication Assurance — nursing station sightlines and handoff zones."""
from __future__ import annotations

from backend.agents.team_utils import has_equipment, make_finding, rooms_from_model

_PATIENT = {"patient_room", "icu_bay", "operating_room"}


async def run(scan_id: str, world_model: dict) -> list[dict]:
    findings: list[dict] = []
    rooms = rooms_from_model(world_model)
    nursing_stations = [r for r in rooms if r.get("type") == "nursing_station"]
    patient_rooms    = [r for r in rooms if r.get("type") in _PATIENT]

    if not nursing_stations:
        for room in patient_rooms:
            findings.append(make_finding(
                scan_id=scan_id, domain="SCA", sub_agent="Handoff-Zone-Auditor", room=room,
                severity="HIGH", confidence=0.85,
                label_text=f"No nursing station — {room['room_id']} has no monitoring hub",
                recommendation="Establish centralised nursing station per TJC LD.04.03.11",
            ))
        return findings

    for ns in nursing_stations:
        if not has_equipment(ns, "workstation"):
            findings.append(make_finding(
                scan_id=scan_id, domain="SCA", sub_agent="Handoff-Zone-Auditor", room=ns,
                severity="HIGH", confidence=0.88,
                label_text=f"Nursing station {ns['room_id']} has no workstation — EHR unavailable",
                recommendation="Install workstation-on-wheels per TJC RC.02.01.01",
                eq_type="workstation",
            ))

    for room in patient_rooms:
        no_sight = not room.get("sightline_to_nursing_station", True)
        no_call  = not has_equipment(room, "call_light")
        if no_sight and no_call:
            findings.append(make_finding(
                scan_id=scan_id, domain="SCA", sub_agent="Handoff-Zone-Auditor", room=room,
                severity="CRITICAL", confidence=0.93,
                label_text=f"{room['room_id']}: no sightline AND no call light — communication blackout",
                recommendation="Install call light + camera feed immediately per CMS §482.13(e) and TJC NPSG.02.03.01",
                eq_type="call_light",   # pin at where call light should be
            ))
    return findings
