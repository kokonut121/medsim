from __future__ import annotations

"""
Scenario simulation runner.

Owns the full lifecycle of a scenario-driven simulation run:
- loads the world model for a unit
- creates / updates the ``ScenarioSimulation`` record in IRIS
- runs the scenario swarm with per-agent trace publishing
- runs the reasoning supervisor with streamed reasoning chunks
- publishes terminal events on the ``simulation:{unit_id}`` Redis channel

Used by both ``backend.api.simulate`` (background task) and tests.
"""

from datetime import datetime, timezone
from uuid import uuid4

from backend.db.iris_client import iris_client
from backend.db.redis_client import redis_client
from backend.models import ScenarioAgentTrace, ScenarioSimulation
from backend.simulation.scenario import run_scenario_swarm
from backend.simulation.scenario_reasoner import reason_scenario_plan


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _resolve_facility_name(unit_id: str) -> str:
    """Mirror the lookup pattern from ``backend/api/optimize.py``."""
    unit = iris_client.units.get(unit_id)
    if unit is None:
        return unit_id
    facility = iris_client.facilities.get(unit.facility_id)
    return facility.name if facility else unit_id


async def _publish(unit_id: str, payload: dict) -> None:
    await redis_client.publish(f"simulation:{unit_id}", payload)


async def run_scenario_simulation(
    unit_id: str,
    scenario_prompt: str,
    agents_per_role: int = 3,
    *,
    simulation_id: str | None = None,
) -> ScenarioSimulation:
    """Full end-to-end run. Persists to IRIS and streams events via Redis."""
    model = iris_client.get_model(unit_id)
    scene_graph = model.scene_graph_json
    facility_name = _resolve_facility_name(unit_id)

    sim_id = simulation_id or f"sim_{uuid4().hex[:8]}"
    existing: ScenarioSimulation | None = iris_client.simulations.get(sim_id)
    if existing is None:
        sim = ScenarioSimulation(
            simulation_id=sim_id,
            unit_id=unit_id,
            status="running",
            scenario_prompt=scenario_prompt,
            agents_per_role=agents_per_role,
            triggered_at=_utcnow(),
        )
        iris_client.write_simulation(sim)
    else:
        sim = iris_client.update_simulation(sim_id, status="running")

    await _publish(unit_id, {"type": "status", "simulation_id": sim_id, "status": "running"})

    async def publish_trace(trace: ScenarioAgentTrace) -> None:
        await _publish(
            unit_id,
            {
                "type": "agent_trace",
                "simulation_id": sim_id,
                **trace.model_dump(),
            },
        )

    try:
        aggregate = await run_scenario_swarm(
            scene_graph,
            facility_name,
            scenario_prompt,
            agents_per_role=agents_per_role,
            on_trace=publish_trace,
        )
    except Exception as exc:
        sim = iris_client.update_simulation(
            sim_id,
            status="failed",
            failure_reason=f"swarm error: {exc}",
            completed_at=_utcnow(),
        )
        await _publish(
            unit_id,
            {"type": "status", "simulation_id": sim_id, "status": "failed", "failure_reason": str(exc)},
        )
        await _publish(
            unit_id,
            {"type": "complete", "simulation_id": sim_id, "simulation": sim.model_dump(mode="json")},
        )
        return sim

    sim = iris_client.update_simulation(
        sim_id,
        status="reasoning",
        swarm_aggregate=aggregate.model_dump(),
    )
    await _publish(unit_id, {"type": "status", "simulation_id": sim_id, "status": "reasoning"})

    async def publish_chunk(chunk: str) -> None:
        await _publish(
            unit_id,
            {"type": "reasoning_chunk", "simulation_id": sim_id, "text": chunk},
        )

    try:
        plan = await reason_scenario_plan(
            scene_graph,
            aggregate,
            scenario_prompt,
            on_chunk=publish_chunk,
        )
    except Exception as exc:
        sim = iris_client.update_simulation(
            sim_id,
            status="failed",
            failure_reason=f"reasoner error: {exc}",
            completed_at=_utcnow(),
        )
        await _publish(
            unit_id,
            {"type": "status", "simulation_id": sim_id, "status": "failed", "failure_reason": str(exc)},
        )
        await _publish(
            unit_id,
            {"type": "complete", "simulation_id": sim_id, "simulation": sim.model_dump(mode="json")},
        )
        return sim

    sim = iris_client.update_simulation(
        sim_id,
        status="complete",
        best_plan=plan.model_dump(),
        completed_at=_utcnow(),
    )
    await _publish(
        unit_id,
        {"type": "complete", "simulation_id": sim_id, "simulation": sim.model_dump(mode="json")},
    )
    return sim
