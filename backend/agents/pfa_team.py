"""Patient Flow Analysis — corridor bottlenecks, clean/dirty traffic merging."""
from __future__ import annotations

from backend.agents.team_utils import (
    make_finding,
    flow_from_model,
    rooms_from_model,
)


async def run(scan_id: str, world_model: dict) -> list[dict]:
    findings: list[dict] = []
    rooms = rooms_from_model(world_model)
    room_map = {r["room_id"]: r for r in rooms}
    flow = flow_from_model(world_model)

    corridors = [r for r in rooms if r.get("type") == "corridor_hallway"]
    clean = set(flow.get("clean_corridors", []))
    dirty = set(flow.get("dirty_corridors", []))

    # Clean and dirty corridors share the same room → traffic merge point
    overlap = clean & dirty
    for room_id in overlap:
        room = room_map.get(room_id)
        if room:
            findings.append(make_finding(
                scan_id=scan_id,
                domain="PFA",
                sub_agent="Discharge-Pathfinder",
                room=room,
                severity="HIGH",
                confidence=0.83,
                label_text=f"Clean and dirty traffic merge at {room_id}",
                recommendation=(
                    "Establish dedicated clean/dirty lanes with floor markings per "
                    "APIC traffic flow separation guidelines"
                ),
            ))

    # Corridors that adjoin both patient rooms and supply/utility — cross-contamination risk
    for corridor in corridors:
        adj = set(corridor.get("adjacency", []))
        adj_types = {room_map[r].get("type") for r in adj if r in room_map}
        if "patient_room" in adj_types and "utility_support" in adj_types:
            findings.append(make_finding(
                scan_id=scan_id,
                domain="PFA",
                sub_agent="Discharge-Pathfinder",
                room=corridor,
                severity="ADVISORY",
                confidence=0.71,
                label_text=f"Corridor {corridor['room_id']} connects patient rooms and utility directly",
                recommendation=(
                    "Add anteroom or visual barrier between patient and utility zones "
                    "per CDC Environmental Infection Control Guidelines §5"
                ),
            ))

    return findings
