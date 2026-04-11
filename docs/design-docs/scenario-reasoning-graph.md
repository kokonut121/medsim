# Scenario Reasoning Graph

The scenario simulation page now renders a live reasoning graph instead of a raw supervisor text panel.

## Contract

- Each `ScenarioAgentTrace` includes graph-ready structure:
  - stable agent identity: `agent_id`, `call_sign`
  - focus room: `focus_room_id`
  - task list: `tasks[]`
  - coordination links: `handoffs[]`
  - encountered blockers: `challenges[]`
- Each completed `ScenarioSimulation` persists a `reasoning_graph` snapshot so refreshes and revisits rehydrate without recomputing UI state. Snapshots are positionless — layout is a client-side concern.
- The simulation websocket emits `graph_update`, `agent_event`, `agent_trace`, `reasoning_chunk`, `status`, and `complete`.

## NDJSON Decision Stream

Each swarm agent emits its decisions one at a time as line-delimited JSON during a single OpenAI streaming completion. The runner buffers chunks, parses complete lines, and rebroadcasts each parsed line as a `ScenarioAgentEvent`. The graph snapshot is recomputed after every event so the frontend can watch the agent reason live.

Per-agent event order is fixed:

1. `focus` — focus room, path through the unit, top-line actions, bottlenecks, resource needs, and patient triage tags.
2. `task` (zero or more) — `ScenarioTask` payload as the agent enumerates local work.
3. `handoff` (zero or more) — `ScenarioHandoff` payload naming a peer agent or fallback role kind.
4. `challenge` (zero or more) — `ScenarioChallenge` payload describing congestion, shortages, or hazards.
5. `note` — short free-text rationale.
6. `done` — final `efficiency_score`.

Within each group, ordering is preserved as the model emits it. Malformed NDJSON lines are dropped silently. After the stream closes the agent's accumulated `ScenarioAgentTrace` is also published via `agent_trace` and finalized in the runner's `streamed_traces` list.

The synthetic fallback (`USE_SYNTHETIC_FALLBACKS=1`) walks each canned trace and emits the same event sequence with small delays, so offline dev exercises the streaming path end to end.

## Live Graph Behavior

- Primary relationship: agent-to-agent handoff edges.
- Secondary context: task chips and challenge chips bloom around each agent node.
- Layout is **incremental force-directed** via [`cytoscape-fcose`](https://github.com/iVis-at-Bilkent/cytoscape.js-fcose) with `randomize: false` so existing nodes stay put while new ones ease into place. The backend never assigns coordinates.
- During the swarm phase, the graph expands as each NDJSON `agent_event` arrives — the snapshot is recomputed and rebroadcast on every event, then a final `agent_trace` upserts the canonical record.
- During the reasoning phase, supervisor insights add highlighted insight nodes and emphasis links over the existing swarm graph.

## Node and Edge Semantics

- `agent` nodes: real role instances in the swarm.
- `task` nodes: local work owned by an agent.
- `challenge` nodes: constraints, congestion, shortages, or hazards reported by an agent.
- `role` nodes: fallback targets when a handoff names only a role type.
- `insight` nodes: supervisor synthesis overlays.

- `handoff` edges: operational coordination between agents or role placeholders.
- `owns` edges: agent-to-task relationship.
- `blocked_by` edges: agent-to-challenge pressure.
- `supports` and `highlight` edges: supervisor overlays that call out critical links.

## Frontend Expectations

- The left panel remains a readable trace feed. It is fed by both `agent_event` (per-decision upserts via the store's `applyAgentEvent` action) and `agent_trace` (final canonical record), so cards fill in their tasks/handoffs/challenges as the agent reasons.
- The right panel is the canonical reasoning surface, rendered with [Cytoscape.js](https://js.cytoscape.org/) + `cytoscape-fcose`. Diff-and-relayout on every snapshot: the renderer adds new elements with `cy.add(...)`, removes anything no longer present, refreshes data on existing nodes, and re-runs the layout in incremental mode so positions ease rather than jump.
- Visual styling pulls from the Sentinel Dossier CSS tokens (`--midnight`, `--bone`, `--signal`, `--ember`, `--phosphor`, `--amber`) at construction via `getComputedStyle(document.documentElement)`.
- If `reasoning_graph` is missing on an older saved simulation, the frontend derives a compatible (positionless) graph from persisted traces once and then renders that fallback. Historical snapshots that still carry `x`/`y` fields parse fine because Pydantic ignores extras and Cytoscape ignores the data attribute.
