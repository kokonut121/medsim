from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.db.iris_client import iris_client
from backend.db.redis_client import redis_client
from backend.models import ScenarioSimulation
from backend.simulation.scenario_runner import run_scenario_simulation


router = APIRouter(tags=["simulate"])


class RunSimulationBody(BaseModel):
    scenario_prompt: str = Field(min_length=5, max_length=500)
    agents_per_role: int = Field(default=3, ge=1, le=8)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@router.post("/api/simulate/{unit_id}/run")
async def trigger_simulation(
    unit_id: str,
    body: RunSimulationBody,
    background_tasks: BackgroundTasks,
) -> dict:
    try:
        model = iris_client.get_model(unit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="World model not found for unit") from exc
    if model.status != "ready":
        raise HTTPException(status_code=409, detail=f"Model is {model.status}, not ready")

    simulation_id = f"sim_{uuid4().hex[:8]}"
    sim = ScenarioSimulation(
        simulation_id=simulation_id,
        unit_id=unit_id,
        status="queued",
        scenario_prompt=body.scenario_prompt,
        agents_per_role=body.agents_per_role,
        triggered_at=_utcnow(),
    )
    iris_client.write_simulation(sim)

    background_tasks.add_task(
        run_scenario_simulation,
        unit_id,
        body.scenario_prompt,
        body.agents_per_role,
        simulation_id=simulation_id,
    )

    return {
        "simulation_id": simulation_id,
        "unit_id": unit_id,
        "status": "queued",
    }


@router.get("/api/simulate/{unit_id}/latest", response_model=ScenarioSimulation)
async def get_latest_simulation(unit_id: str) -> ScenarioSimulation:
    try:
        return iris_client.get_latest_simulation(unit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="No simulations for unit") from exc


@router.get("/api/simulate/{unit_id}/list", response_model=list[ScenarioSimulation])
async def list_simulations(unit_id: str) -> list[ScenarioSimulation]:
    return iris_client.list_simulations(unit_id)


@router.get("/api/simulate/{unit_id}/{simulation_id}", response_model=ScenarioSimulation)
async def get_simulation(unit_id: str, simulation_id: str) -> ScenarioSimulation:
    try:
        sim = iris_client.get_simulation(simulation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Simulation not found") from exc
    if sim.unit_id != unit_id:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim


@router.websocket("/ws/simulate/{unit_id}/live")
async def websocket_simulation_live(websocket: WebSocket, unit_id: str):
    """
    Live stream of agent traces, reasoning chunks, and status transitions for
    the scenario pathway. Uses a 300s idle timeout (the scan WS in
    ``backend/api/websocket.py`` caps at 30s, which is too short here) and
    terminates cleanly on the terminal ``complete`` event.
    """
    await websocket.accept()
    channel = f"simulation:{unit_id}"
    queue = await redis_client.subscribe(channel)
    try:
        while True:
            payload = await asyncio.wait_for(queue.get(), timeout=300)
            await websocket.send_json(payload)
            if isinstance(payload, dict) and payload.get("type") == "complete":
                break
    except (asyncio.TimeoutError, WebSocketDisconnect):
        pass
    finally:
        redis_client.unsubscribe(channel, queue)
        try:
            await websocket.close()
        except Exception:
            pass
