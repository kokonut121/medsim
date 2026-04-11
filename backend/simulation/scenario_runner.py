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
from backend.models import (
    ScenarioAgentEvent,
    ScenarioAgentTrace,
    ScenarioGraphEdge,
    ScenarioGraphNode,
    ScenarioGraphSnapshot,
    ScenarioSimulation,
    SupervisorInsight,
)
from backend.agents.swarm import _bundle_text as _bt
from backend.pipeline.spatial_bundle import build_spatial_bundle
from backend.simulation.scenario import run_scenario_swarm
from backend.simulation.scenario_reasoner import reason_scenario_plan


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _summarize_findings(findings) -> str:
    """Compact summary of baseline safety findings for scenario prompt injection."""
    if not findings:
        return "No prior safety findings."
    lines = ["Baseline safety findings:"]
    for f in sorted(findings, key=lambda x: getattr(x, "compound_severity", 0), reverse=True)[:10]:
        lines.append(f"  [{f.severity}] {f.room_id}: {f.label_text}")
    return "\n".join(lines)


def _resolve_facility_name(unit_id: str) -> str:
    """Mirror the lookup pattern from ``backend/api/optimize.py``."""
    unit = iris_client.units.get(unit_id)
    if unit is None:
        return unit_id
    facility = iris_client.facilities.get(unit.facility_id)
    return facility.name if facility else unit_id


async def _publish(unit_id: str, payload: dict) -> None:
    await redis_client.publish(f"simulation:{unit_id}", payload)


def _graph_from_traces(
    traces: list[ScenarioAgentTrace],
    *,
    phase: str,
    step: int,
    insights: list[SupervisorInsight] | None = None,
) -> ScenarioGraphSnapshot:
    """Build a positionless snapshot. Layout is computed client-side by Cytoscape."""
    nodes: list[ScenarioGraphNode] = []
    edges: list[ScenarioGraphEdge] = []
    highlights: list[str] = []
    traces_by_id = {trace.agent_id: trace for trace in traces}

    for trace in traces:
        agent_detail = trace.notes or ", ".join(trace.actions[:2])
        nodes.append(
            ScenarioGraphNode(
                id=trace.agent_id,
                kind="agent",
                label=trace.call_sign or trace.role_label,
                role_kind=trace.kind,
                room_id=trace.focus_room_id,
                emphasis="high" if any(item.blocking for item in trace.challenges) else "medium",
                detail=agent_detail[:240],
                revealed_at_step=step,
            )
        )

        for task in trace.tasks[:4]:
            task_id = f"{trace.agent_id}:task:{task.task_id}"
            nodes.append(
                ScenarioGraphNode(
                    id=task_id,
                    kind="task",
                    label=task.label,
                    role_kind=trace.kind,
                    room_id=task.room_id,
                    parent_id=trace.agent_id,
                    emphasis=task.priority,
                    detail=f"{task.status} task",
                    revealed_at_step=step,
                )
            )
            edges.append(
                ScenarioGraphEdge(
                    id=f"{trace.agent_id}:owns:{task.task_id}",
                    source=trace.agent_id,
                    target=task_id,
                    kind="owns",
                    label=task.status,
                    revealed_at_step=step,
                )
            )

        for challenge in trace.challenges[:4]:
            challenge_id = f"{trace.agent_id}:challenge:{challenge.challenge_id}"
            nodes.append(
                ScenarioGraphNode(
                    id=challenge_id,
                    kind="challenge",
                    label=challenge.label,
                    role_kind=trace.kind,
                    room_id=challenge.room_id,
                    parent_id=trace.agent_id,
                    emphasis=challenge.severity,
                    detail=challenge.impact[:240],
                    revealed_at_step=step,
                )
            )
            edges.append(
                ScenarioGraphEdge(
                    id=f"{trace.agent_id}:blocked_by:{challenge.challenge_id}",
                    source=trace.agent_id,
                    target=challenge_id,
                    kind="blocked_by",
                    label="blocking" if challenge.blocking else "pressure",
                    revealed_at_step=step,
                )
            )
            if challenge.blocking:
                highlights.append(challenge_id)

        for handoff_index, handoff in enumerate(trace.handoffs[:4]):
            target_id = handoff.target_agent_id
            if not target_id and handoff.target_kind:
                target_id = f"role:{handoff.target_kind}"
                if target_id not in {node.id for node in nodes}:
                    nodes.append(
                        ScenarioGraphNode(
                            id=target_id,
                            kind="role",
                            label=handoff.target_kind.replace("_", " "),
                            role_kind=handoff.target_kind,
                            room_id=handoff.room_id,
                            emphasis=handoff.urgency,
                            detail="Role-level fallback target",
                            revealed_at_step=step,
                        )
                    )
            if target_id:
                edges.append(
                    ScenarioGraphEdge(
                        id=f"{trace.agent_id}:handoff:{handoff_index}:{target_id}",
                        source=trace.agent_id,
                        target=target_id,
                        kind="handoff",
                        label=handoff.reason[:80],
                        urgency=handoff.urgency,
                        revealed_at_step=step,
                    )
                )

    for insight in insights or []:
        insight_id = f"insight:{insight.insight_id}"
        nodes.append(
            ScenarioGraphNode(
                id=insight_id,
                kind="insight",
                label=insight.title,
                room_id=insight.room_id,
                emphasis=insight.emphasis,
                detail=insight.summary[:240],
                revealed_at_step=step,
            )
        )
        highlights.append(insight_id)
        for source_agent_id in insight.source_agent_ids[:3]:
            if source_agent_id in traces_by_id:
                edges.append(
                    ScenarioGraphEdge(
                        id=f"{insight_id}:support:{source_agent_id}",
                        source=source_agent_id,
                        target=insight_id,
                        kind="supports",
                        label=insight.kind.replace("_", " "),
                        urgency=insight.emphasis,
                        revealed_at_step=step,
                    )
                )
        for target_agent_id in insight.target_agent_ids[:3]:
            if target_agent_id in traces_by_id:
                edges.append(
                    ScenarioGraphEdge(
                        id=f"{insight_id}:highlight:{target_agent_id}",
                        source=insight_id,
                        target=target_agent_id,
                        kind="highlight",
                        label="priority link",
                        urgency=insight.emphasis,
                        revealed_at_step=step,
                    )
                )

    return ScenarioGraphSnapshot(
        phase=phase,
        step=step,
        nodes=nodes,
        edges=edges,
        highlighted_node_ids=list(dict.fromkeys(highlights)),
        narrative="Supervisor highlights applied." if insights else "Live agent graph expanding.",
    )


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

    # Build (or reuse) canonical spatial bundle
    spatial_bundle = model.spatial_bundle_json
    if not spatial_bundle:
        spatial_bundle = build_spatial_bundle(scene_graph)
        iris_client.update_model(model.model_id, spatial_bundle_json=spatial_bundle)

    # Gather latest baseline findings to annotate scenario prompts
    baseline_findings = iris_client.list_findings(unit_id)
    baseline_summary = _summarize_findings(baseline_findings)

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
    # partial_traces holds the in-flight per-agent state as decision events
    # arrive; finalized_ids gates the upgrade from partial to canonical trace.
    partial_traces: dict[str, ScenarioAgentTrace] = {}
    finalized_ids: set[str] = set()
    streamed_traces: list[ScenarioAgentTrace] = []
    graph_step = 0

    def _current_trace_set() -> list[ScenarioAgentTrace]:
        # Use the canonical finalized trace if available, otherwise the in-flight partial.
        out: list[ScenarioAgentTrace] = []
        seen: set[str] = set()
        for trace in streamed_traces:
            out.append(trace)
            seen.add(trace.agent_id)
        for agent_id, partial in partial_traces.items():
            if agent_id not in seen:
                out.append(partial)
        return out

    def _ensure_partial(event: ScenarioAgentEvent) -> ScenarioAgentTrace:
        partial = partial_traces.get(event.agent_id)
        if partial is None:
            partial = ScenarioAgentTrace(
                agent_index=event.agent_index,
                agent_id=event.agent_id,
                call_sign=event.call_sign or event.agent_id,
                kind=event.agent_kind,
                role_label=event.role_label or event.agent_kind,
            )
            partial_traces[event.agent_id] = partial
        return partial

    async def publish_event(event: ScenarioAgentEvent) -> None:
        nonlocal graph_step
        if event.agent_id in finalized_ids:
            # Late event for an already-finalized agent — ignore.
            return
        partial = _ensure_partial(event)
        if event.kind == "focus":
            partial.focus_room_id = event.focus_room_id
            partial.path = list(event.path)
            partial.actions = list(event.actions)
            partial.bottlenecks = list(event.bottlenecks)
            partial.resource_needs = list(event.resource_needs)
            partial.patient_tags = list(event.patient_tags)
        elif event.kind == "task" and event.task is not None:
            partial.tasks.append(event.task)
        elif event.kind == "handoff" and event.handoff is not None:
            partial.handoffs.append(event.handoff)
        elif event.kind == "challenge" and event.challenge is not None:
            partial.challenges.append(event.challenge)
        elif event.kind == "note" and event.note is not None:
            partial.notes = event.note
        elif event.kind == "done" and event.efficiency_score is not None:
            partial.efficiency_score = event.efficiency_score

        graph_step += 1
        snapshot = _graph_from_traces(_current_trace_set(), phase="running", step=graph_step)
        await _publish(
            unit_id,
            {
                "type": "agent_event",
                "simulation_id": sim_id,
                "event": event.model_dump(),
            },
        )
        await _publish(
            unit_id,
            {
                "type": "graph_update",
                "simulation_id": sim_id,
                "snapshot": snapshot.model_dump(),
            },
        )

    async def publish_trace(trace: ScenarioAgentTrace) -> None:
        nonlocal graph_step, sim
        streamed_traces.append(trace)
        finalized_ids.add(trace.agent_id)
        partial_traces.pop(trace.agent_id, None)
        graph_step += 1
        snapshot = _graph_from_traces(_current_trace_set(), phase="running", step=graph_step)
        sim = iris_client.update_simulation(sim_id, reasoning_graph=snapshot.model_dump())
        await _publish(
            unit_id,
            {
                "type": "agent_trace",
                "simulation_id": sim_id,
                **trace.model_dump(),
            },
        )
        await _publish(
            unit_id,
            {
                "type": "graph_update",
                "simulation_id": sim_id,
                "snapshot": snapshot.model_dump(),
            },
        )

    # Gather active patient intakes for this unit and embed a summary into
    # the scenario prompt so agents know which patients are inbound.
    patient_context = ""
    try:
        intakes = iris_client.list_patient_intakes(unit_id)
        if intakes:
            lines = [f"  - [{i.injury_severity.upper()}] {i.chief_complaint}"
                     + (f" (ETA {i.eta_minutes} min)" if i.eta_minutes else "")
                     + (f" — {i.mechanism}" if i.mechanism else "")
                     for i in intakes[:10]]
            patient_context = "\n--- INCOMING PATIENTS (pre-hospital FHIR intakes) ---\n" + "\n".join(lines)
    except Exception:
        pass

    # Augment the scenario prompt with spatial bundle summary + baseline findings
    # so every role agent reasons over the annotated facility state.
    augmented_prompt = (
        f"{scenario_prompt}\n\n"
        f"--- FACILITY SPATIAL CONTEXT ---\n{_bt(spatial_bundle)}\n\n"
        f"--- KNOWN SAFETY ISSUES ---\n{baseline_summary}"
        f"{patient_context}"
    )

    try:
        aggregate = await run_scenario_swarm(
            scene_graph,
            facility_name,
            augmented_prompt,
            agents_per_role=agents_per_role,
            on_trace=publish_trace,
            on_event=publish_event,
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
        reasoning_graph=(sim.reasoning_graph.model_dump() if sim.reasoning_graph else None),
    )
    await _publish(unit_id, {"type": "status", "simulation_id": sim_id, "status": "reasoning"})
    graph_step += 1
    reasoning_snapshot = _graph_from_traces(aggregate.traces, phase="reasoning", step=graph_step)
    sim = iris_client.update_simulation(sim_id, reasoning_graph=reasoning_snapshot.model_dump())
    await _publish(
        unit_id,
        {
            "type": "graph_update",
            "simulation_id": sim_id,
            "snapshot": reasoning_snapshot.model_dump(),
        },
    )

    async def publish_chunk(chunk: str) -> None:
        await _publish(
            unit_id,
            {"type": "reasoning_chunk", "simulation_id": sim_id, "text": chunk},
        )

    try:
        result = await reason_scenario_plan(
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

    graph_step += 1
    insight_snapshot = _graph_from_traces(
        aggregate.traces,
        phase="reasoning",
        step=graph_step,
        insights=result.supervisor_insights,
    )
    sim = iris_client.update_simulation(
        sim_id,
        status="complete",
        best_plan=result.best_plan.model_dump(),
        reasoning_graph=insight_snapshot.model_dump(),
        completed_at=_utcnow(),
    )
    await _publish(
        unit_id,
        {
            "type": "graph_update",
            "simulation_id": sim_id,
            "snapshot": insight_snapshot.model_dump(),
        },
    )
    await _publish(
        unit_id,
        {"type": "complete", "simulation_id": sim_id, "simulation": sim.model_dump(mode="json")},
    )
    return sim
