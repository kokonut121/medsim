from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.db.iris_client import iris_client
from backend.db.r2_client import r2_client
from backend.pipeline.fal_generator import generate_floor_plan
from backend.simulation.optimizer import optimize_layout
from backend.simulation.swarm import run_swarm


router = APIRouter(prefix="/api/optimize", tags=["optimize"])


@router.post("/{unit_id}")
async def run_optimization(unit_id: str, agents_per_role: int = 5):
    """
    Run swarm simulation + gpt-4o reasoning on the world model for a unit.

    1. Pulls the current scene graph from the world model.
    2. Runs `agents_per_role × 6` gpt-4o-mini swarm agents in parallel.
    3. Feeds aggregated swarm data to gpt-4o for layout optimization reasoning.
    4. Regenerates the floor plan via fal.ai using the optimized layout description.
    5. Stores the optimized floor plan back in R2 and returns the full result.
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

    # 1. Swarm simulation
    swarm_report = await run_swarm(
        scene_graph,
        facility_name,
        agents_per_role=agents_per_role,
    )

    # 2. Reasoning layer
    optimization = await optimize_layout(scene_graph, swarm_report)

    # 3. Regenerate floor plan with optimized layout prompt
    floor_plan_prompt_override = optimization.get("floor_plan_prompt")
    if floor_plan_prompt_override:
        floor_plan_bytes = await generate_floor_plan(
            optimization.get("optimized_scene_graph", scene_graph),
            facility_name,
            prompt_override=floor_plan_prompt_override,
        )
    else:
        floor_plan_bytes = await generate_floor_plan(
            optimization.get("optimized_scene_graph", scene_graph),
            facility_name,
        )

    # 4. Store optimized floor plan in R2
    key = f"facilities/{unit_id}/floor_plan_optimized.png"
    r2_client.upload_bytes(key, floor_plan_bytes, content_type="image/png")
    optimized_floor_plan_url = r2_client.public_url_for(key)

    # 5. Patch the optimized scene graph with the new floor plan URL
    optimized_sg = optimization.get("optimized_scene_graph", scene_graph)
    optimized_sg["floor_plan_url"] = optimized_floor_plan_url
    optimized_sg["optimized"] = True

    # Update the model's scene graph so reports pick up the optimized layout
    iris_client.update_model(model.model_id, scene_graph_json=optimized_sg)

    return {
        "unit_id": unit_id,
        "facility_name": facility_name,
        "agents_run": swarm_report.agents_run,
        "avg_efficiency_before": swarm_report.avg_efficiency,
        "efficiency_gain_estimate": optimization.get("efficiency_gain_estimate"),
        "summary": optimization.get("summary"),
        "bottleneck_analysis": optimization.get("bottleneck_analysis", []),
        "equipment_relocations": optimization.get("equipment_relocations", []),
        "room_adjacency_changes": optimization.get("room_adjacency_changes", []),
        "dead_zone_repurposing": optimization.get("dead_zone_repurposing", []),
        "optimized_floor_plan_url": optimized_floor_plan_url,
        "swarm_report": swarm_report.to_dict(),
    }
