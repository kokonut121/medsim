from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.agents.consensus import SEVERITY_SCORES

# ---------------------------------------------------------------------------
# Grid → world-space coordinate mapping
# ---------------------------------------------------------------------------
_GRID_SCALE = 0.8
_COL_ORIGIN = 2.0
_ROW_ORIGIN = 1.5
_HALF       = _GRID_SCALE * 0.35   # intra-room offset radius

# Default heights per equipment type (metres above floor)
_EQ_HEIGHT: dict[str, float] = {
    "hand_hygiene_dispenser": 1.2,  # wall-mounted at arm reach
    "crash_cart":             0.9,  # wheeled, top of cart
    "monitor":                1.8,  # wall/ceiling arm
    "ventilator":             1.1,  # floor unit, control panel height
    "iv_pole":                1.4,  # hanging bag height
    "call_light":             0.85, # bed-rail button
    "workstation":            1.0,  # desk height
    "adc":                    1.15, # dispensing cabinet drawer height
    "defibrillator":          1.0,
    "crash_cart":             0.9,
}
_DEFAULT_HEIGHT = 1.0


def _parse_position_offset(pos: str) -> tuple[float, float, float]:
    """
    Parse a natural-language position string from the scene graph into a
    (dx, dy, dz) offset within the room's grid cell.

    Convention: +X = right/east, -X = left/west, +Z = far wall, -Z = entry/door.
    """
    p = pos.lower()
    dx, dy, dz = 0.0, 0.0, 0.0

    # Horizontal placement
    if "right" in p:
        dx += _HALF
    if "left" in p:
        dx -= _HALF

    # Depth placement
    if any(w in p for w in ("door", "entry", "entry")):
        dz -= _HALF          # near the door = front of room
    if any(w in p for w in ("back wall", "far end", "back")):
        dz += _HALF          # rear of room
    if any(w in p for w in ("bedside", "head of")):
        dz += _HALF * 0.5

    # Height overrides from position string
    if any(w in p for w in ("ceiling", "overhead", "ceiling arm", "ceiling boom")):
        dy = 2.3 - _DEFAULT_HEIGHT   # pull up to ceiling
    elif any(w in p for w in ("wall mount", "wall")):
        dy = 1.35 - _DEFAULT_HEIGHT
    elif any(w in p for w in ("floor", "ground")):
        dy = 0.15 - _DEFAULT_HEIGHT

    return dx, dy, dz


def equipment_world_pos(
    room: dict,
    eq_type: str,
) -> tuple[float, float, float]:
    """
    Return the 3D world position of a specific equipment item inside a room,
    derived from the room's grid coordinates + the equipment's position string.
    """
    col = room.get("grid_col", 0)
    row = room.get("grid_row", 0)

    base_x = (col - _COL_ORIGIN) * _GRID_SCALE
    base_z = (row - _ROW_ORIGIN) * _GRID_SCALE
    base_y = _EQ_HEIGHT.get(eq_type, _DEFAULT_HEIGHT)

    # Find the equipment entry
    eq = next((e for e in room.get("equipment", []) if e["type"] == eq_type), None)
    pos_str = (eq or {}).get("position", "")

    dx, dy, dz = _parse_position_offset(pos_str)

    return (
        round(base_x + dx, 3),
        round(base_y + dy, 3),
        round(base_z + dz, 3),
    )


def room_center_pos(room: dict) -> tuple[float, float, float]:
    """World position at the centre of a room at standing height."""
    col = room.get("grid_col", 0)
    row = room.get("grid_row", 0)
    x = (col - _COL_ORIGIN) * _GRID_SCALE
    z = (row - _ROW_ORIGIN) * _GRID_SCALE
    return (round(x, 3), _DEFAULT_HEIGHT, round(z, 3))


# ---------------------------------------------------------------------------
# Scene-graph helpers
# ---------------------------------------------------------------------------

def rooms_from_model(world_model: dict) -> list[dict]:
    sg = world_model.get("scene_graph_json", {})
    return [r for unit in sg.get("units", []) for r in unit.get("rooms", [])]


def flow_from_model(world_model: dict) -> dict:
    sg = world_model.get("scene_graph_json", {})
    return sg.get("flow_annotations", {})


def has_equipment(room: dict, eq_type: str) -> bool:
    return any(e["type"] == eq_type for e in room.get("equipment", []))


def accessible_equipment(room: dict, eq_type: str) -> bool:
    for e in room.get("equipment", []):
        if e["type"] == eq_type:
            return e.get("accessible", True)
    return False


# ---------------------------------------------------------------------------
# Finding factory
# ---------------------------------------------------------------------------

def make_finding(
    *,
    scan_id: str,
    domain: str,
    sub_agent: str,
    room: dict,
    severity: str,
    confidence: float,
    label_text: str,
    recommendation: str,
    eq_type: str | None = None,   # when set, pin goes on the actual equipment
) -> dict:
    if eq_type:
        x, y, z = equipment_world_pos(room, eq_type)
    else:
        x, y, z = room_center_pos(room)

    return {
        "finding_id": f"finding_{uuid4().hex[:8]}",
        "scan_id": scan_id,
        "domain": domain,
        "sub_agent": sub_agent,
        "room_id": room["room_id"],
        "severity": severity,
        "severity_score": SEVERITY_SCORES[severity],
        "compound_severity": SEVERITY_SCORES[severity],
        "label_text": label_text,
        "spatial_anchor": {"x": x, "y": y, "z": z},
        "confidence": confidence,
        "evidence_r2_keys": [f"scene_graph:{room['room_id']}:{eq_type or 'room'}"],
        "recommendation": recommendation,
        "compound_domains": [domain],
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
