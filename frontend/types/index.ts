export type Domain = "ICA" | "MSA" | "FRA" | "ERA" | "PFA" | "SCA";
export type Severity = "CRITICAL" | "HIGH" | "ADVISORY";
export type ModelStatus = "queued" | "acquiring" | "classifying" | "generating" | "ready" | "failed";
export type ImageSource = "street_view" | "places" | "supplemental_upload" | "world_labs" | "vr_video";

export interface SpatialAnchor {
  x: number;
  y: number;
  z: number;
}

export interface Finding {
  finding_id: string;
  scan_id: string;
  domain: Domain;
  sub_agent: string;
  room_id: string;
  severity: Severity;
  compound_severity: number;
  label_text: string;
  spatial_anchor: SpatialAnchor;
  confidence: number;
  evidence_r2_keys: string[];
  recommendation: string;
  compound_domains: Domain[];
  created_at: string;
}

export interface Scan {
  scan_id: string;
  unit_id: string;
  model_id: string | null;
  status: "queued" | "running" | "synthesizing" | "complete" | "failed";
  domain_statuses: Record<Domain, { status: string; finding_count: number }>;
  findings: Finding[];
  triggered_at: string;
  completed_at: string | null;
}

export interface Facility {
  facility_id: string;
  name: string;
  address: string;
  lat: number;
  lng: number;
  org_id: string;
  google_place_id: string;
  osm_building_id: string;
  created_at: string;
}

export interface Unit {
  unit_id: string;
  facility_id: string;
  name: string;
  floor: number;
  unit_type: string;
  created_at: string;
}

export interface WorldModel {
  model_id: string;
  unit_id: string;
  status: ModelStatus;
  splat_r2_key: string;
  scene_graph_json: Record<string, unknown>;
  world_labs_world_id: string;
  source_image_count?: number;
  failure_reason?: string | null;
  caption?: string | null;
  thumbnail_url?: string | null;
  world_marble_url?: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ModelStatusResponse {
  unit_id: string;
  model_id: string;
  status: ModelStatus;
  failure_reason: string | null;
  source_image_count: number;
  caption: string | null;
  thumbnail_url: string | null;
  world_marble_url: string | null;
  completed_at: string | null;
}

export interface FacilityCreateInput {
  name: string;
  address: string;
  unit_name?: string;
  unit_type?: string;
  floor?: number;
}

export interface CoverageArea {
  area_id: string;
  source: ImageSource | string;
  image_count: number;
  category: string | null;
}

export interface GapArea {
  area_id: string;
  description: string;
}

export interface CoverageMap {
  facility_id: string;
  covered_areas: CoverageArea[];
  gap_areas: GapArea[];
  updated_at: string | null;
}

export interface FacilityImage {
  image_id: string;
  url: string;
  source: ImageSource | string;
  category: string | null;
  heading: number | null;
  content_type: string;
}

// ---------------------------------------------------------------------------
// Scenario simulation pathway
// ---------------------------------------------------------------------------

export type SimulationStatus = "queued" | "running" | "reasoning" | "complete" | "failed";
export type InjurySeverity = "immediate" | "delayed" | "minor" | "expectant";
export type TaskStatus = "queued" | "active" | "blocked" | "complete";
export type TaskPriority = "critical" | "high" | "medium" | "low";
export type HandoffUrgency = "critical" | "high" | "medium" | "low";
export type ChallengeSeverity = "critical" | "high" | "medium" | "low";
export type SupervisorInsightKind = "shared_bottleneck" | "critical_handoff" | "overload" | "reroute";
export type GraphNodeKind = "agent" | "task" | "challenge" | "role" | "insight";
export type GraphEdgeKind = "handoff" | "owns" | "blocked_by" | "supports" | "highlight";
export type ScenarioAgentKind =
  | "incident_commander"
  | "triage_officer"
  | "burn_specialist"
  | "trauma_surgeon"
  | "anesthesiologist"
  | "resource_allocator"
  | "scenario_patient"
  | "nurse"
  | "doctor";

export interface ScenarioTask {
  task_id: string;
  label: string;
  room_id: string | null;
  status: TaskStatus;
  priority: TaskPriority;
}

export interface ScenarioHandoff {
  target_agent_id: string | null;
  target_kind: ScenarioAgentKind | null;
  reason: string;
  room_id: string | null;
  urgency: HandoffUrgency;
}

export interface ScenarioChallenge {
  challenge_id: string;
  label: string;
  room_id: string | null;
  severity: ChallengeSeverity;
  impact: string;
  blocking: boolean;
}

export interface SupervisorInsight {
  insight_id: string;
  kind: SupervisorInsightKind;
  title: string;
  summary: string;
  room_id: string | null;
  source_agent_ids: string[];
  target_agent_ids: string[];
  emphasis: ChallengeSeverity;
}

export interface ScenarioGraphNode {
  id: string;
  kind: GraphNodeKind;
  label: string;
  role_kind: ScenarioAgentKind | null;
  room_id: string | null;
  parent_id: string | null;
  emphasis: string | null;
  detail: string;
  revealed_at_step: number;
}

export interface ScenarioGraphEdge {
  id: string;
  source: string;
  target: string;
  kind: GraphEdgeKind;
  label: string;
  urgency: string | null;
  revealed_at_step: number;
}

export interface ScenarioGraphSnapshot {
  version: number;
  phase: string;
  step: number;
  nodes: ScenarioGraphNode[];
  edges: ScenarioGraphEdge[];
  highlighted_node_ids: string[];
  narrative: string;
}

export interface ScenarioAgentTrace {
  agent_index: number;
  agent_id: string;
  call_sign: string;
  kind: ScenarioAgentKind;
  role_label: string;
  focus_room_id: string | null;
  actions: string[];
  path: string[];
  bottlenecks: string[];
  resource_needs: string[];
  patient_tags: InjurySeverity[];
  tasks: ScenarioTask[];
  handoffs: ScenarioHandoff[];
  challenges: ScenarioChallenge[];
  notes: string;
  efficiency_score: number;
}

export type ScenarioAgentEventKind =
  | "focus"
  | "task"
  | "handoff"
  | "challenge"
  | "note"
  | "done";

export interface ScenarioAgentEvent {
  agent_id: string;
  agent_index: number;
  agent_kind: ScenarioAgentKind;
  call_sign: string;
  role_label: string;
  kind: ScenarioAgentEventKind;
  seq: number;
  // focus payload
  focus_room_id: string | null;
  path: string[];
  actions: string[];
  bottlenecks: string[];
  resource_needs: string[];
  patient_tags: InjurySeverity[];
  // task / handoff / challenge payloads
  task: ScenarioTask | null;
  handoff: ScenarioHandoff | null;
  challenge: ScenarioChallenge | null;
  // note payload
  note: string | null;
  // done payload
  efficiency_score: number | null;
}

export interface ScenarioSwarmAggregate {
  facility_name: string;
  scenario_prompt: string;
  agents_run: number;
  agents_per_role: number;
  path_frequency: Record<string, number>;
  bottleneck_counts: Record<string, number>;
  resource_need_counts: Record<string, number>;
  triage_mix: Partial<Record<InjurySeverity, number>>;
  avg_efficiency: number;
  efficiency_by_kind: Record<string, number>;
  traces: ScenarioAgentTrace[];
}

export interface StaffPlacement {
  room_id: string;
  kind: ScenarioAgentKind | string;
  count: number;
  rationale: string;
}

export interface ResourceAllocationItem {
  resource: string;
  source_room_id: string | null;
  destination_room_id: string;
  quantity: number;
  rationale: string;
}

export interface TriagePriority {
  tier: InjurySeverity;
  destination_room_id: string;
  routing_rule: string;
  staff_required: string[];
}

export interface TimelinePhase {
  phase_label: string;
  actions: string[];
  decision_points: string[];
}

export interface BestPlan {
  staff_placement: StaffPlacement[];
  resource_allocation: ResourceAllocationItem[];
  triage_priorities: TriagePriority[];
  timeline: TimelinePhase[];
  summary: string;
  assumptions: string[];
}

export interface ScenarioReasonerResult {
  best_plan: BestPlan;
  supervisor_insights: SupervisorInsight[];
}

export interface ScenarioSimulation {
  simulation_id: string;
  unit_id: string;
  status: SimulationStatus;
  scenario_prompt: string;
  agents_per_role: number;
  triggered_at: string;
  completed_at: string | null;
  failure_reason: string | null;
  swarm_aggregate: ScenarioSwarmAggregate | null;
  reasoning_graph: ScenarioGraphSnapshot | null;
  best_plan: BestPlan | null;
}

export interface RunSimulationResponse {
  simulation_id: string;
  unit_id: string;
  status: SimulationStatus;
}

export type SimulationWsEvent =
  | {
      type: "status";
      simulation_id: string;
      status: SimulationStatus;
      failure_reason?: string;
    }
  | ({ type: "agent_trace"; simulation_id: string } & ScenarioAgentTrace)
  | { type: "agent_event"; simulation_id: string; event: ScenarioAgentEvent }
  | { type: "graph_update"; simulation_id: string; snapshot: ScenarioGraphSnapshot }
  | { type: "reasoning_chunk"; simulation_id: string; text: string }
  | { type: "complete"; simulation_id: string; simulation: ScenarioSimulation };
