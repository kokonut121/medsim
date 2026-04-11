"use client";

import type {
  ScenarioAgentTrace,
  ScenarioGraphEdge,
  ScenarioGraphNode,
  ScenarioGraphSnapshot
} from "@/types";

/**
 * Reconstructs a positionless `ScenarioGraphSnapshot` from persisted traces.
 *
 * Used as a fallback for completed simulations whose `reasoning_graph` field
 * is missing or empty (live runs render the snapshot the backend publishes).
 * Coordinates are computed client-side by Cytoscape's fcose layout, so this
 * function only emits structural data.
 */
export function deriveReasoningGraph(
  traces: ScenarioAgentTrace[],
  phase = "running"
): ScenarioGraphSnapshot {
  const nodes: ScenarioGraphNode[] = [];
  const edges: ScenarioGraphEdge[] = [];
  const seenRoleNodes = new Set<string>();

  for (const trace of traces) {
    nodes.push({
      id: trace.agent_id,
      kind: "agent",
      label: trace.call_sign || trace.role_label,
      role_kind: trace.kind,
      room_id: trace.focus_room_id,
      parent_id: null,
      emphasis: trace.challenges.some((item) => item.blocking) ? "high" : "medium",
      detail: trace.notes || trace.actions.slice(0, 2).join(", "),
      revealed_at_step: traces.length
    });

    trace.tasks.slice(0, 4).forEach((task) => {
      const taskId = `${trace.agent_id}:task:${task.task_id}`;
      nodes.push({
        id: taskId,
        kind: "task",
        label: task.label,
        role_kind: trace.kind,
        room_id: task.room_id,
        parent_id: trace.agent_id,
        emphasis: task.priority,
        detail: `${task.status} task`,
        revealed_at_step: traces.length
      });
      edges.push({
        id: `${trace.agent_id}:owns:${task.task_id}`,
        source: trace.agent_id,
        target: taskId,
        kind: "owns",
        label: task.status,
        urgency: null,
        revealed_at_step: traces.length
      });
    });

    trace.challenges.slice(0, 4).forEach((challenge) => {
      const challengeId = `${trace.agent_id}:challenge:${challenge.challenge_id}`;
      nodes.push({
        id: challengeId,
        kind: "challenge",
        label: challenge.label,
        role_kind: trace.kind,
        room_id: challenge.room_id,
        parent_id: trace.agent_id,
        emphasis: challenge.severity,
        detail: challenge.impact,
        revealed_at_step: traces.length
      });
      edges.push({
        id: `${trace.agent_id}:blocked_by:${challenge.challenge_id}`,
        source: trace.agent_id,
        target: challengeId,
        kind: "blocked_by",
        label: challenge.blocking ? "blocking" : "pressure",
        urgency: null,
        revealed_at_step: traces.length
      });
    });

    trace.handoffs.slice(0, 4).forEach((handoff, index) => {
      let targetId = handoff.target_agent_id;
      if (!targetId && handoff.target_kind) {
        targetId = `role:${handoff.target_kind}`;
        if (!seenRoleNodes.has(targetId)) {
          seenRoleNodes.add(targetId);
          nodes.push({
            id: targetId,
            kind: "role",
            label: handoff.target_kind.replaceAll("_", " "),
            role_kind: handoff.target_kind,
            room_id: handoff.room_id,
            parent_id: null,
            emphasis: handoff.urgency,
            detail: "Role-level fallback target",
            revealed_at_step: traces.length
          });
        }
      }
      if (!targetId) return;
      edges.push({
        id: `${trace.agent_id}:handoff:${index}:${targetId}`,
        source: trace.agent_id,
        target: targetId,
        kind: "handoff",
        label: handoff.reason,
        urgency: handoff.urgency,
        revealed_at_step: traces.length
      });
    });
  }

  const highlightedNodeIds = nodes
    .filter((node) => node.kind === "challenge" && node.emphasis === "critical")
    .map((node) => node.id);

  return {
    version: 1,
    phase,
    step: traces.length,
    nodes,
    edges,
    highlighted_node_ids: highlightedNodeIds,
    narrative: "Derived from persisted traces."
  };
}
