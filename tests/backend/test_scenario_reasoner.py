"""
Tests for the scenario reasoning supervisor (synthetic fallback path).
"""
from __future__ import annotations

import asyncio

import pytest

from backend.config import get_settings
from backend.models import ScenarioAgentTrace, ScenarioReasonerResult, ScenarioSwarmAggregate
from backend.simulation.scenario_reasoner import reason_scenario_plan


@pytest.fixture(autouse=True)
def force_synthetic_fallback(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "use_synthetic_fallbacks", True)
    monkeypatch.setattr(settings, "openai_api_key", "")
    yield


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _fixture_aggregate() -> ScenarioSwarmAggregate:
    traces = [
        ScenarioAgentTrace(
            agent_index=0,
            kind="incident_commander",
            role_label="Incident Commander",
            actions=["stand up command"],
            path=["TC-NS", "TC-CORRIDOR"],
            bottlenecks=["single-lane entry"],
            resource_needs=["radio handsets"],
            notes="command staged",
            efficiency_score=7.0,
        ),
        ScenarioAgentTrace(
            agent_index=1,
            kind="scenario_patient",
            role_label="Patient",
            path=["TC-ENTRY", "TC-RESUS"],
            patient_tags=["immediate"],
            efficiency_score=4.0,
        ),
    ]
    return ScenarioSwarmAggregate(
        facility_name="Test Trauma Center",
        scenario_prompt="burn casualties from factory fire",
        agents_run=2,
        agents_per_role=1,
        path_frequency={"TB-1": 10, "TC-RESUS": 8, "TC-NS": 4},
        bottleneck_counts={"single-lane entry at TC-ENTRY": 3},
        resource_need_counts={"O-neg blood": 5, "burn kits": 4, "ventilators": 3},
        triage_mix={"immediate": 2, "delayed": 1, "minor": 1, "expectant": 1},
        avg_efficiency=5.5,
        efficiency_by_kind={"incident_commander": 7.0, "scenario_patient": 4.0},
        traces=traces,
    )


def test_reason_scenario_plan_returns_best_plan(demo_world_model):
    aggregate = _fixture_aggregate()
    plan = _run(
        reason_scenario_plan(
            demo_world_model,
            aggregate,
            "burn casualties from factory fire",
        )
    )
    assert isinstance(plan, ScenarioReasonerResult)
    assert plan.best_plan.staff_placement, "staff_placement must be populated"
    assert plan.best_plan.resource_allocation, "resource_allocation must be populated"
    assert plan.supervisor_insights, "supervisor insights must be populated"


def test_reason_scenario_plan_covers_all_triage_tiers(demo_world_model):
    aggregate = _fixture_aggregate()
    plan = _run(
        reason_scenario_plan(
            demo_world_model,
            aggregate,
            "burn casualties from factory fire",
        )
    )
    tiers = {tp.tier for tp in plan.best_plan.triage_priorities}
    assert tiers == {"immediate", "delayed", "minor", "expectant"}


def test_reason_scenario_plan_has_three_timeline_phases(demo_world_model):
    aggregate = _fixture_aggregate()
    plan = _run(
        reason_scenario_plan(
            demo_world_model,
            aggregate,
            "burn casualties from factory fire",
        )
    )
    labels = [phase.phase_label for phase in plan.best_plan.timeline]
    assert len(labels) >= 3
    # The synthetic path produces exactly these three phase labels.
    assert "T+0-5 min" in labels
    assert "T+5-30 min" in labels
    assert "T+30-60 min" in labels


def test_reason_scenario_plan_streams_chunks(demo_world_model):
    aggregate = _fixture_aggregate()
    chunks: list[str] = []

    async def collect(chunk: str) -> None:
        chunks.append(chunk)

    _run(
        reason_scenario_plan(
            demo_world_model,
            aggregate,
            "burn casualties",
            on_chunk=collect,
        )
    )
    assert len(chunks) >= 2


def test_reason_scenario_plan_adds_burn_specialist_for_burn_scenario(demo_world_model):
    aggregate = _fixture_aggregate()
    plan = _run(
        reason_scenario_plan(
            demo_world_model,
            aggregate,
            "mass burn casualties from factory fire",
        )
    )
    kinds = {placement.kind for placement in plan.best_plan.staff_placement}
    assert "burn_specialist" in kinds


def test_reason_scenario_plan_skips_burn_specialist_for_non_burn(demo_world_model):
    aggregate = _fixture_aggregate()
    plan = _run(
        reason_scenario_plan(
            demo_world_model,
            aggregate,
            "stabbing victim influx from street altercation",
        )
    )
    kinds = {placement.kind for placement in plan.best_plan.staff_placement}
    assert "burn_specialist" not in kinds
