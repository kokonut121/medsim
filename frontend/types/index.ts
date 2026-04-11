export type Domain = "ICA" | "MSA" | "FRA" | "ERA" | "PFA" | "SCA";
export type Severity = "CRITICAL" | "HIGH" | "ADVISORY";
export type ModelStatus = "queued" | "acquiring" | "classifying" | "generating" | "ready" | "failed";

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

// ---------------------------------------------------------------------------
// Scenario simulation pathway
// ---------------------------------------------------------------------------

export type SimulationStatus = "queued" | "running" | "reasoning" | "complete" | "failed";
export type InjurySeverity = "immediate" | "delayed" | "minor" | "expectant";
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

export interface ScenarioAgentTrace {
  agent_index: number;
  kind: ScenarioAgentKind;
  role_label: string;
  actions: string[];
  path: string[];
  bottlenecks: string[];
  resource_needs: string[];
  patient_tags: InjurySeverity[];
  notes: string;
  efficiency_score: number;
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
  | { type: "reasoning_chunk"; simulation_id: string; text: string }
  | { type: "complete"; simulation_id: string; simulation: ScenarioSimulation };
