"""Medication Safety Assurance — ADC and workstation in medication rooms."""
from __future__ import annotations

from backend.agents.team_utils import accessible_equipment, has_equipment, make_finding, rooms_from_model


async def run(scan_id: str, world_model: dict) -> list[dict]:
    findings: list[dict] = []
    for room in rooms_from_model(world_model):
        if room.get("type") != "medication_room_pharmacy":
            continue
        if not has_equipment(room, "adc"):
            findings.append(make_finding(
                scan_id=scan_id, domain="MSA", sub_agent="MedSafe-Auditor", room=room,
                severity="HIGH", confidence=0.89,
                label_text=f"No ADC in {room['room_id']}",
                recommendation="Install ADC per USP <797> §5.1 controlled-substance security",
                eq_type="adc",
            ))
        elif not accessible_equipment(room, "adc"):
            findings.append(make_finding(
                scan_id=scan_id, domain="MSA", sub_agent="MedSafe-Auditor", room=room,
                severity="HIGH", confidence=0.87,
                label_text=f"ADC in {room['room_id']} blocked",
                recommendation="Clear 36-inch aisle in front of ADC per ISMP §6",
                eq_type="adc",
            ))
        if not has_equipment(room, "workstation"):
            findings.append(make_finding(
                scan_id=scan_id, domain="MSA", sub_agent="MedSafe-Auditor", room=room,
                severity="ADVISORY", confidence=0.74,
                label_text=f"No med-prep workstation in {room['room_id']}",
                recommendation="Add wall-mounted workstation with barcode scanner per ISMP guidelines",
                eq_type="workstation",
            ))
    return findings
