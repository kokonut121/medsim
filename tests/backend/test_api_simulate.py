"""
API integration tests for the scenario simulation pathway.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from backend.config import get_settings


@pytest.fixture(autouse=True)
def force_synthetic_fallback(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "use_synthetic_fallbacks", True)
    monkeypatch.setattr(settings, "openai_api_key", "")
    yield


def _wait_for_completion(client, unit_id: str, timeout: float = 5.0) -> dict:
    """Poll GET /latest until status is terminal or timeout elapses."""
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/simulate/{unit_id}/latest")
        if response.status_code == 200:
            last = response.json()
            if last.get("status") in ("complete", "failed"):
                return last
        # Yield to the running background task
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.05))
    return last


def test_post_run_returns_queued(client, fresh_iris, seeded_unit_id):
    response = client.post(
        f"/api/simulate/{seeded_unit_id}/run",
        json={"scenario_prompt": "burn casualties from factory fire", "agents_per_role": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["unit_id"] == seeded_unit_id
    assert body["status"] == "queued"
    assert body["simulation_id"].startswith("sim_")


def test_post_run_then_latest_eventually_completes(client, fresh_iris, seeded_unit_id):
    response = client.post(
        f"/api/simulate/{seeded_unit_id}/run",
        json={"scenario_prompt": "burn casualties from factory fire", "agents_per_role": 2},
    )
    assert response.status_code == 200

    final = _wait_for_completion(client, seeded_unit_id, timeout=5.0)
    assert final.get("status") == "complete", final
    assert final.get("best_plan") is not None
    assert final.get("swarm_aggregate") is not None
    assert final.get("reasoning_graph") is not None

    plan = final["best_plan"]
    tiers = {tp["tier"] for tp in plan["triage_priorities"]}
    assert tiers == {"immediate", "delayed", "minor", "expectant"}
    assert len(plan["timeline"]) >= 3


def test_post_run_rejects_unknown_unit(client, fresh_iris):
    response = client.post(
        "/api/simulate/unit_does_not_exist/run",
        json={"scenario_prompt": "burn casualties", "agents_per_role": 2},
    )
    assert response.status_code == 404


def test_post_run_rejects_short_prompt(client, fresh_iris, seeded_unit_id):
    response = client.post(
        f"/api/simulate/{seeded_unit_id}/run",
        json={"scenario_prompt": "x", "agents_per_role": 2},
    )
    assert response.status_code == 422


def test_list_simulations_filters_by_unit(client, fresh_iris, seeded_unit_id):
    client.post(
        f"/api/simulate/{seeded_unit_id}/run",
        json={"scenario_prompt": "first burn scenario", "agents_per_role": 1},
    )
    _wait_for_completion(client, seeded_unit_id, timeout=5.0)
    client.post(
        f"/api/simulate/{seeded_unit_id}/run",
        json={"scenario_prompt": "second burn scenario", "agents_per_role": 1},
    )
    _wait_for_completion(client, seeded_unit_id, timeout=5.0)

    response = client.get(f"/api/simulate/{seeded_unit_id}/list")
    assert response.status_code == 200
    sims = response.json()
    assert len(sims) >= 2
    assert all(sim["unit_id"] == seeded_unit_id for sim in sims)


def test_get_latest_404_when_no_runs(client, fresh_iris, seeded_unit_id):
    response = client.get(f"/api/simulate/{seeded_unit_id}/latest")
    assert response.status_code == 404


def test_ws_streams_agent_events_before_agent_trace(client, fresh_iris, seeded_unit_id):
    """The live WS should emit ``agent_event`` messages while an agent is still
    streaming its NDJSON decisions, and a matching ``agent_trace`` after the
    agent finalizes."""
    with client.websocket_connect(f"/ws/simulate/{seeded_unit_id}/live") as ws:
        response = client.post(
            f"/api/simulate/{seeded_unit_id}/run",
            json={"scenario_prompt": "burn casualties from factory fire", "agents_per_role": 1},
        )
        assert response.status_code == 200

        agent_event_seen_before_trace = False
        agent_event_count = 0
        agent_trace_count = 0
        graph_update_count = 0
        first_trace_agent: str | None = None
        completed = False

        # Cap the loop generously — synthetic runs are fast but include sleeps.
        for _ in range(2000):
            try:
                payload = ws.receive_json(mode="text")
            except Exception:
                break
            ptype = payload.get("type")
            if ptype == "agent_event":
                agent_event_count += 1
                if first_trace_agent is None:
                    agent_event_seen_before_trace = True
            elif ptype == "agent_trace":
                agent_trace_count += 1
                if first_trace_agent is None:
                    first_trace_agent = payload.get("agent_id")
            elif ptype == "graph_update":
                graph_update_count += 1
            elif ptype == "complete":
                completed = True
                break

        assert completed, "WS did not deliver a complete message"
        assert agent_event_count > 0, "no agent_event messages over WS"
        assert agent_trace_count > 0, "no agent_trace messages over WS"
        assert graph_update_count > 0, "no graph_update messages over WS"
        assert agent_event_seen_before_trace, (
            "agent_trace arrived before any agent_event — graph would not be live"
        )
