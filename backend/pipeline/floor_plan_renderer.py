from __future__ import annotations

"""
Deterministic floor plan renderer.

Renders the scene graph as a precise architectural floor plan — rooms and walls
are fixed from the scene graph structure and never change between renders.
Only equipment markers move between before/after views.

Uses matplotlib so output is pixel-perfect and reproducible.
"""

import io
import math
from dataclasses import dataclass, field

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.patches import FancyArrowPatch


# ---------------------------------------------------------------------------
# Room type styling
# ---------------------------------------------------------------------------

ROOM_COLORS = {
    "patient_room":             "#dce8f5",
    "nursing_station":          "#d4edda",
    "medication_room_pharmacy": "#fff3cd",
    "icu_bay":                  "#f8d7da",
    "operating_room":           "#e8d5f5",
    "corridor_hallway":         "#f0f0f0",
    "ed_entrance_ambulance_bay":"#fde8d0",
    "lobby_main_entrance":      "#e0f0e0",
    "utility_support":          "#e8e8e8",
    "other":                    "#f5f5f5",
}

ROOM_LABELS = {
    "patient_room":             "Patient\nRoom",
    "nursing_station":          "Nursing\nStation",
    "medication_room_pharmacy": "Med\nRoom",
    "icu_bay":                  "ICU Bay",
    "operating_room":           "OR",
    "corridor_hallway":         "Corridor",
    "ed_entrance_ambulance_bay":"ED\nEntrance",
    "lobby_main_entrance":      "Lobby",
    "utility_support":          "Utility",
    "other":                    "Room",
}

# Equipment icon + color
EQUIPMENT_STYLE = {
    "crash_cart":               ("CC", "#c0392b", "Crash Cart"),
    "hand_hygiene_dispenser":   ("HH", "#27ae60", "Hand Hygiene"),
    "adc":                      ("Rx", "#8e44ad", "Med Dispenser"),
    "workstation":              ("WS", "#2980b9", "Workstation"),
    "call_light":               ("CL", "#f39c12", "Call Light"),
    "iv_pole":                  ("IV", "#16a085", "IV Pole"),
    "monitor":                  ("MN", "#2c3e50", "Monitor"),
    "ventilator":               ("VT", "#e74c3c", "Ventilator"),
}

EQUIPMENT_DEFAULT = ("EQ", "#7f8c8d", "Equipment")


# ---------------------------------------------------------------------------
# Layout engine — auto-positions rooms from adjacency graph
# ---------------------------------------------------------------------------

@dataclass
class RoomRect:
    room_id: str
    room_type: str
    x: float
    y: float
    w: float
    h: float
    equipment: list[dict] = field(default_factory=list)
    sightline: bool = False


def _estimate_size(area_sqft: float) -> tuple[float, float]:
    """Convert sqft estimate to plot units (1 unit ≈ 10 ft)."""
    side = math.sqrt(max(area_sqft, 80)) / 10
    if area_sqft >= 300:
        return (side * 1.4, side * 0.8)
    return (side, side)


def _layout_rooms(rooms: list[dict]) -> list[RoomRect]:
    """
    Place rooms in a grid layout respecting adjacency hints.
    Corridors are placed as wide horizontal strips.
    """
    if not rooms:
        return []

    placed: dict[str, RoomRect] = {}
    cols = max(3, math.ceil(math.sqrt(len(rooms))))
    grid_x, grid_y = 0.5, 0.5
    col, row = 0, 0
    row_height = 0.0

    for room in rooms:
        area = room.get("area_sqft_estimate", 150)
        w, h = _estimate_size(area)

        # Corridors span full width
        if room.get("type") in ("corridor_hallway", "ed_entrance_ambulance_bay"):
            if col > 0:
                row += 1
                grid_x = 0.5
                grid_y += row_height + 0.3
                row_height = 0.0
                col = 0
            w = cols * 2.2
            h = 0.9

        rect = RoomRect(
            room_id=room["room_id"],
            room_type=room.get("type", "other"),
            x=grid_x,
            y=grid_y,
            w=w,
            h=h,
            equipment=room.get("equipment", []),
            sightline=room.get("sightline_to_nursing_station", False),
        )
        placed[room["room_id"]] = rect

        grid_x += w + 0.3
        row_height = max(row_height, h)
        col += 1
        if col >= cols and room.get("type") not in ("corridor_hallway",):
            col = 0
            row += 1
            grid_x = 0.5
            grid_y += row_height + 0.3
            row_height = 0.0

    return list(placed.values())


# ---------------------------------------------------------------------------
# Equipment overlay — given relocations, patch positions
# ---------------------------------------------------------------------------

def _apply_relocations(
    rects: list[RoomRect],
    equipment_relocations: list[dict],
) -> list[RoomRect]:
    """
    Move equipment items to their recommended rooms.
    Only touches equipment — room geometry is unchanged.
    """
    if not equipment_relocations:
        return rects

    room_map = {r.room_id: r for r in rects}

    for relocation in equipment_relocations:
        equip_type = relocation.get("equipment", "").lower().replace(" ", "_")
        target_room_hint = relocation.get("recommended_position", "").lower()

        # Find source room containing this equipment
        source = None
        for rect in rects:
            for eq in rect.equipment:
                if equip_type in eq.get("type", "").lower():
                    source = rect
                    break
            if source:
                break

        if not source:
            continue

        # Find target room — match by room_id or type hint
        target = None
        for rect in rects:
            if rect.room_id.lower() in target_room_hint or rect.room_type.lower() in target_room_hint:
                target = rect
                break
        if not target:
            # Fall back to nursing station for most equipment moves
            for rect in rects:
                if rect.room_type == "nursing_station":
                    target = rect
                    break

        if target and target.room_id != source.room_id:
            # Move equipment from source to target
            moved = [eq for eq in source.equipment if equip_type in eq.get("type", "").lower()]
            source.equipment = [eq for eq in source.equipment if equip_type not in eq.get("type", "").lower()]
            target.equipment.extend(moved)

    return rects


# ---------------------------------------------------------------------------
# Core render
# ---------------------------------------------------------------------------

def _render(
    rects: list[RoomRect],
    title: str,
    flow_annotations: dict,
    *,
    show_sightlines: bool = True,
) -> bytes:
    if not rects:
        return b""

    all_x = [r.x + r.w for r in rects]
    all_y = [r.y + r.h for r in rects]
    fig_w = max(all_x) + 1.0
    fig_h = max(all_y) + 1.5

    fig, ax = plt.subplots(figsize=(fig_w * 1.2, fig_h * 1.2))
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("#fafafa")

    # Title
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12, color="#1a3c5e")

    # Draw flow corridors as subtle arrows
    clean = flow_annotations.get("clean_corridors", [])
    dirty = flow_annotations.get("dirty_corridors", [])
    for rect in rects:
        if rect.room_id in clean:
            ax.add_patch(mpatches.FancyBboxPatch(
                (rect.x - 0.05, rect.y - 0.05), rect.w + 0.1, rect.h + 0.1,
                boxstyle="round,pad=0.05", linewidth=2,
                edgecolor="#2ecc71", facecolor="none", linestyle="--", alpha=0.6, zorder=1,
            ))
        if rect.room_id in dirty:
            ax.add_patch(mpatches.FancyBboxPatch(
                (rect.x - 0.05, rect.y - 0.05), rect.w + 0.1, rect.h + 0.1,
                boxstyle="round,pad=0.05", linewidth=2,
                edgecolor="#e74c3c", facecolor="none", linestyle="--", alpha=0.6, zorder=1,
            ))

    # Draw rooms (fixed architecture)
    for rect in rects:
        color = ROOM_COLORS.get(rect.room_type, "#f5f5f5")
        wall = mpatches.FancyBboxPatch(
            (rect.x, rect.y), rect.w, rect.h,
            boxstyle="square,pad=0",
            linewidth=2.5, edgecolor="#2c3e50", facecolor=color, zorder=2,
        )
        ax.add_patch(wall)

        # Room label
        label = ROOM_LABELS.get(rect.room_type, "Room")
        ax.text(
            rect.x + rect.w / 2, rect.y + rect.h * 0.72,
            f"{rect.room_id}\n{label}",
            ha="center", va="center", fontsize=7, color="#2c3e50",
            fontweight="semibold", zorder=4,
            multialignment="center",
        )

        # Sightline indicator
        if show_sightlines and rect.sightline:
            ax.text(
                rect.x + rect.w - 0.12, rect.y + rect.h - 0.15,
                "👁", fontsize=7, ha="right", va="top", zorder=5,
            )

    # Draw equipment (movable layer)
    for rect in rects:
        n_eq = len(rect.equipment)
        if n_eq == 0:
            continue
        eq_xs = [rect.x + rect.w * (i + 1) / (n_eq + 1) for i in range(n_eq)]
        eq_y = rect.y + rect.h * 0.28

        for eq, ex in zip(rect.equipment, eq_xs):
            eq_type = eq.get("type", "other")
            icon, color, label = EQUIPMENT_STYLE.get(eq_type, EQUIPMENT_DEFAULT)
            accessible = eq.get("accessible", True)
            alpha = 1.0 if accessible else 0.4

            # Equipment dot
            ax.plot(ex, eq_y, "o", markersize=10, color=color, alpha=alpha, zorder=6)
            ax.text(ex, eq_y, icon, ha="center", va="center", fontsize=6, zorder=7)
            ax.text(
                ex, eq_y - 0.22, label,
                ha="center", va="top", fontsize=5.5, color=color,
                fontweight="bold", zorder=7,
            )

    # Legend
    legend_items = []
    seen = set()
    for rect in rects:
        for eq in rect.equipment:
            eq_type = eq.get("type", "other")
            if eq_type not in seen:
                _, color, label = EQUIPMENT_STYLE.get(eq_type, EQUIPMENT_DEFAULT)
                legend_items.append(mpatches.Patch(color=color, label=label))
                seen.add(eq_type)

    if legend_items:
        ax.legend(
            handles=legend_items,
            loc="lower left", fontsize=7, framealpha=0.85,
            title="Equipment", title_fontsize=7,
            bbox_to_anchor=(0.01, 0.01),
        )

    # Clean/dirty corridor legend
    ax.plot([], [], "--", color="#2ecc71", linewidth=2, label="Clean corridor")
    ax.plot([], [], "--", color="#e74c3c", linewidth=2, label="Dirty corridor")

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#fafafa")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_floor_plan(scene_graph: dict, title: str = "Floor Plan") -> bytes:
    """Render the current floor plan from the scene graph. Architecture is fixed."""
    rooms: list[dict] = []
    for unit in scene_graph.get("units", []):
        rooms.extend(unit.get("rooms", []))

    rects = _layout_rooms(rooms)
    return _render(rects, title, scene_graph.get("flow_annotations", {}))


def render_optimized_floor_plan(
    scene_graph: dict,
    equipment_relocations: list[dict],
    title: str = "Optimized Floor Plan",
) -> bytes:
    """
    Render the optimized floor plan.
    Room geometry is IDENTICAL to render_floor_plan — only equipment positions change.
    """
    rooms: list[dict] = []
    for unit in scene_graph.get("units", []):
        rooms.extend(unit.get("rooms", []))

    rects = _layout_rooms(rooms)
    rects = _apply_relocations(rects, equipment_relocations)
    return _render(rects, title, scene_graph.get("flow_annotations", {}))
