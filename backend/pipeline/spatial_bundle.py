"""
Canonical Spatial Bundle
========================
Derives a structured, LLM-readable spatial bundle from a raw scene-graph JSON.
This is the *sole* input contract for all domain swarm agents and scenario swarms.

LLMs must emit room_id / equipment_ref references, never raw coordinates.
The grounding layer (backend.agents.grounding) snaps those references to anchors
stored here.
"""
from __future__ import annotations

import math

_GRID_SCALE = 3.5
_COL_ORIGIN = 0.86
_ROW_ORIGIN = 0.5
_HALF = _GRID_SCALE * 0.35

# Heights for model a97601cc (ground_plane_offset=1.467, metric_scale=0.913)
# Y = 1.467 - real_height_m / 0.913
_EQ_HEIGHT: dict[str, float] = {
    "hand_hygiene_dispenser": 0.15,
    "crash_cart":             0.48,
    "monitor":               -0.51,
    "ventilator":             0.26,
    "iv_pole":               -0.07,
    "call_light":             0.54,
    "workstation":            0.37,
    "adc":                    0.21,
    "defibrillator":          0.37,
}
_DEFAULT_HEIGHT = 0.37


def _grid_center(room: dict) -> dict[str, float]:
    col = float(room.get("grid_col", 0))
    row = float(room.get("grid_row", 0))
    return {
        "x": round((col - _COL_ORIGIN) * _GRID_SCALE, 3),
        "y": _DEFAULT_HEIGHT,
        "z": round((row - _ROW_ORIGIN) * _GRID_SCALE, 3),
    }


def _parse_position_offset(pos: str) -> tuple[float, float, float]:
    p = (pos or "").lower()
    dx, dy, dz = 0.0, 0.0, 0.0
    if "right" in p:
        dx += _HALF
    if "left" in p:
        dx -= _HALF
    if any(w in p for w in ("door", "entry")):
        dz -= _HALF
    if any(w in p for w in ("back wall", "far end", "back")):
        dz += _HALF
    if any(w in p for w in ("bedside", "head of")):
        dz += _HALF * 0.5
    if any(w in p for w in ("ceiling", "overhead", "ceiling arm", "ceiling boom")):
        dy = 2.3 - _DEFAULT_HEIGHT
    elif any(w in p for w in ("wall mount", "wall")):
        dy = 1.35 - _DEFAULT_HEIGHT
    elif any(w in p for w in ("floor", "ground")):
        dy = 0.15 - _DEFAULT_HEIGHT
    return dx, dy, dz


def _eq_anchor(room: dict, eq: dict) -> dict[str, float]:
    center = _grid_center(room)
    eq_type = eq.get("type", "")
    height = _EQ_HEIGHT.get(eq_type, _DEFAULT_HEIGHT)
    dx, dy, dz = _parse_position_offset(eq.get("position", ""))
    return {
        "x": round(center["x"] + dx, 3),
        "y": round(height + dy, 3),
        "z": round(center["z"] + dz, 3),
    }


def _zone_tags(room: dict, flow_annotations: dict) -> list[str]:
    tags: list[str] = []
    room_id = room.get("room_id", "")
    room_type = (room.get("type") or "").lower()

    if room_id in flow_annotations.get("clean_corridors", []):
        tags.append("clean_corridor")
    if room_id in flow_annotations.get("dirty_corridors", []):
        tags.append("dirty_corridor")
    if any(k in room_type for k in ("patient", "icu", "sim", "bay", "resus")):
        tags.append("patient_care")
    if any(k in room_type for k in ("medication", "pharmacy")):
        tags.append("medication")
    if "nursing_station" in room_type:
        tags.append("nursing_hub")
    if any(k in room_type for k in ("corridor", "hall")):
        tags.append("circulation")
    if any(k in room_type for k in ("utility", "supply")):
        tags.append("utility")
    if any(k in room_type for k in ("entry", "lobby", "entrance")):
        tags.append("entry")
    if any(k in room_type for k in ("debrief", "consult", "conference", "skills")):
        tags.append("consultation")
    if any(k in room_type for k in ("control", "monitor")):
        tags.append("control_room")

    return tags


def build_spatial_bundle(
    scene_graph: dict,
    floor_plan_ref: str | None = None,
) -> dict:
    """
    Derive a canonical spatial bundle from a scene-graph JSON dict.

    Returns a dict with keys:
      unit_id, floor_plan_ref, rooms, room_index (internal), nav_edges,
      visibility_pairs, zone_index, flow_annotations
    """
    units = scene_graph.get("units", [])
    unit_id: str = units[0]["unit_id"] if units else "unknown"

    all_rooms: list[dict] = []
    for unit in units:
        all_rooms.extend(unit.get("rooms", []))

    flow_annotations: dict = scene_graph.get("flow_annotations", {})

    # --- Build room list ---
    bundle_rooms: list[dict] = []
    room_index: dict[str, dict] = {}

    for room in all_rooms:
        center = _grid_center(room)
        equipment_anchors: list[dict] = []

        for eq in room.get("equipment", []):
            equipment_anchors.append({
                "type": eq.get("type"),
                "accessible": eq.get("accessible", True),
                "confidence": eq.get("confidence", 0.8),
                "anchor": _eq_anchor(room, eq),
                "position_hint": eq.get("position", ""),
            })

        bundle_room = {
            "room_id": room["room_id"],
            "type": room.get("type", "unknown"),
            "zone_tags": _zone_tags(room, flow_annotations),
            "center": center,
            "area_sqft": room.get("area_sqft_estimate", 0),
            "adjacency": room.get("adjacency", []),
            "sightline_to_nursing_station": room.get("sightline_to_nursing_station", True),
            "equipment": equipment_anchors,
        }
        bundle_rooms.append(bundle_room)
        room_index[room["room_id"]] = bundle_room

    # --- Nav edges from adjacency ---
    nav_edges: list[dict] = []
    seen_edges: set[frozenset] = set()

    for room in bundle_rooms:
        for neighbor_id in room["adjacency"]:
            edge_key = frozenset([room["room_id"], neighbor_id])
            if edge_key in seen_edges or neighbor_id not in room_index:
                continue
            seen_edges.add(edge_key)
            neighbor = room_index[neighbor_id]
            c1, c2 = room["center"], neighbor["center"]
            dist_m = round(math.sqrt((c1["x"] - c2["x"]) ** 2 + (c1["z"] - c2["z"]) ** 2), 3)
            nav_edges.append({"from": room["room_id"], "to": neighbor_id, "distance_m": dist_m})

    # --- Visibility pairs ---
    visibility_pairs: list[dict] = []
    nursing_rooms = [r["room_id"] for r in bundle_rooms if "nursing_hub" in r["zone_tags"]]

    for room in bundle_rooms:
        if room.get("sightline_to_nursing_station") and nursing_rooms:
            for ns_id in nursing_rooms:
                visibility_pairs.append({"observer": room["room_id"], "observed": ns_id})

    # --- Zone index ---
    zone_index: dict[str, list[str]] = {r["room_id"]: r["zone_tags"] for r in bundle_rooms}

    return {
        "unit_id": unit_id,
        "floor_plan_ref": floor_plan_ref,
        "rooms": bundle_rooms,
        "room_index": room_index,  # fast lookup — stripped before LLM prompts
        "nav_edges": nav_edges,
        "visibility_pairs": visibility_pairs,
        "zone_index": zone_index,
        "flow_annotations": flow_annotations,
    }
