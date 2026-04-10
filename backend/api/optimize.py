from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.db.iris_client import iris_client
from backend.db.r2_client import r2_client
from backend.pipeline.floor_plan_renderer import render_floor_plan, render_optimized_floor_plan
from backend.simulation.optimizer import optimize_layout
from backend.simulation.swarm import run_swarm


router = APIRouter(prefix="/api/optimize", tags=["optimize"])


@router.post("/{unit_id}")
async def run_optimization(unit_id: str, agents_per_role: int = 5):
    """
    Run swarm simulation + gpt-4o reasoning on the world model for a unit.

    1. Renders the current floor plan deterministically from the scene graph (fixed walls).
    2. Runs agents_per_role × 6 gpt-4o-mini swarm agents in parallel.
    3. Feeds aggregated swarm data to gpt-4o — only equipment/furniture moves suggested.
    4. Renders the optimized floor plan with identical room geometry, moved equipment only.
    5. Stores both before/after to R2 and returns full diff.
    """
    try:
        model = iris_client.get_model(unit_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="World model not found for unit")

    if model.status != "ready":
        raise HTTPException(status_code=409, detail=f"Model is {model.status}, not ready")

    scene_graph = model.scene_graph_json
    facility = next(
        (f for f in iris_client.facilities.values()
         if any(u.unit_id == unit_id for u in iris_client.units.values() if u.facility_id == f.facility_id)),
        None,
    )
    facility_name = facility.name if facility else unit_id

    # 1. Render BEFORE — fixed architecture, current equipment positions
    before_bytes = render_floor_plan(scene_graph, title=f"{facility_name} — Current Layout")
    before_key = f"facilities/{unit_id}/floor_plan_before.png"
    r2_client.upload_bytes(before_key, before_bytes, content_type="image/png")
    before_url = r2_client.public_url_for(before_key)

    # 2. Swarm simulation
    swarm_report = await run_swarm(scene_graph, facility_name, agents_per_role=agents_per_role)

    # 3. Reasoning layer (equipment moves only)
    optimization = await optimize_layout(scene_graph, swarm_report)
    equipment_relocations = optimization.get("equipment_relocations", [])

    # 4. Render AFTER — identical room geometry, equipment moved
    after_bytes = render_optimized_floor_plan(
        scene_graph,
        equipment_relocations,
        title=f"{facility_name} — Optimized Layout",
    )
    after_key = f"facilities/{unit_id}/floor_plan_after.png"
    r2_client.upload_bytes(after_key, after_bytes, content_type="image/png")
    after_url = r2_client.public_url_for(after_key)

    # 5. Update model scene graph
    optimized_sg = dict(scene_graph)
    optimized_sg["floor_plan_url"] = after_url
    optimized_sg["floor_plan_before_url"] = before_url
    optimized_sg["equipment_relocations"] = equipment_relocations
    optimized_sg["optimized"] = True
    iris_client.update_model(model.model_id, scene_graph_json=optimized_sg)

    return {
        "unit_id": unit_id,
        "facility_name": facility_name,
        "agents_run": swarm_report.agents_run,
        "avg_efficiency_before": swarm_report.avg_efficiency,
        "efficiency_gain_estimate": optimization.get("efficiency_gain_estimate"),
        "summary": optimization.get("summary"),
        "bottleneck_analysis": optimization.get("bottleneck_analysis", []),
        "equipment_relocations": equipment_relocations,
        "room_adjacency_changes": optimization.get("room_adjacency_changes", []),
        "dead_zone_repurposing": optimization.get("dead_zone_repurposing", []),
        "before_floor_plan_url": before_url,
        "after_floor_plan_url": after_url,
        "swarm_report": swarm_report.to_dict(),
    }
