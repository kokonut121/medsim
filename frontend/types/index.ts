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
  status: "queued" | "running" | "synthesizing" | "complete" | "failed";
  domain_statuses: Record<Domain, { status: string; finding_count: number }>;
  findings: Finding[];
  triggered_at: string;
  completed_at: string | null;
}

export interface CoverageMap {
  facility_id: string;
  covered_areas: Array<{ area_id: string; source: string; image_count: number; category?: string | null }>;
  gap_areas: Array<{ area_id: string; description: string }>;
  updated_at?: string | null;
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
