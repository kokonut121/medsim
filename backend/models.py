from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Domain = Literal["ICA", "MSA", "FRA", "ERA", "PFA", "SCA"]
Severity = Literal["CRITICAL", "HIGH", "ADVISORY"]
ModelStatus = Literal["queued", "acquiring", "classifying", "generating", "ready", "failed"]
ScanStatus = Literal["queued", "running", "synthesizing", "complete", "failed"]
ImageSource = Literal["street_view", "places", "supplemental_upload", "world_labs", "vr_video"]


class SpatialAnchor(BaseModel):
    x: float
    y: float
    z: float


class Finding(BaseModel):
    finding_id: str
    scan_id: str
    domain: Domain
    sub_agent: str
    room_id: str
    severity: Severity
    compound_severity: float = Field(ge=0.0, le=1.0)
    label_text: str
    spatial_anchor: SpatialAnchor
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_r2_keys: list[str]
    recommendation: str
    compound_domains: list[Domain]
    created_at: datetime


class DomainStatus(BaseModel):
    status: str
    finding_count: int
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Scan(BaseModel):
    scan_id: str
    unit_id: str
    status: ScanStatus
    domain_statuses: dict[Domain, DomainStatus]
    findings: list[Finding]
    triggered_at: datetime
    completed_at: datetime | None = None


class CoverageArea(BaseModel):
    area_id: str
    source: str
    image_count: int
    category: str | None = None


class GapArea(BaseModel):
    area_id: str
    description: str


class CoverageMap(BaseModel):
    facility_id: str
    covered_areas: list[CoverageArea]
    gap_areas: list[GapArea]
    updated_at: datetime | None = None


class ImageMeta(BaseModel):
    image_id: str
    facility_id: str
    source: ImageSource
    r2_key: str
    public_url: str
    category: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    heading: int | None = None
    notes: str | None = None
    content_type: str = "image/jpeg"
    created_at: datetime


class Facility(BaseModel):
    facility_id: str
    name: str
    address: str
    lat: float
    lng: float
    org_id: str
    google_place_id: str
    osm_building_id: str
    created_at: datetime


class Unit(BaseModel):
    unit_id: str
    facility_id: str
    name: str
    floor: int
    unit_type: str
    created_at: datetime


class WorldModel(BaseModel):
    model_id: str
    unit_id: str
    status: ModelStatus
    splat_r2_key: str
    scene_graph_json: dict
    world_labs_world_id: str
    source_image_count: int = 0
    failure_reason: str | None = None
    caption: str | None = None
    thumbnail_url: str | None = None
    world_marble_url: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class FacilityCreate(BaseModel):
    name: str
    address: str
    unit_name: str | None = None
    unit_type: str | None = None
    floor: int = 1
    lat: float | None = None
    lng: float | None = None
    google_place_id: str | None = None
    osm_building_id: str | None = None


# ---------------------------------------------------------------------------
# Scenario-driven simulation pathway
# ---------------------------------------------------------------------------

SimulationStatus = Literal["queued", "running", "reasoning", "complete", "failed"]
InjurySeverity = Literal["immediate", "delayed", "minor", "expectant"]
ScenarioAgentKind = Literal[
    "incident_commander",
    "triage_officer",
    "burn_specialist",
    "trauma_surgeon",
    "anesthesiologist",
    "resource_allocator",
    "scenario_patient",
    "nurse",
    "doctor",
]


class ScenarioAgentTrace(BaseModel):
    agent_index: int
    kind: ScenarioAgentKind
    role_label: str
    actions: list[str] = Field(default_factory=list)
    path: list[str] = Field(default_factory=list)
    bottlenecks: list[str] = Field(default_factory=list)
    resource_needs: list[str] = Field(default_factory=list)
    patient_tags: list[InjurySeverity] = Field(default_factory=list)
    notes: str = ""
    efficiency_score: float = Field(default=5.0, ge=0.0, le=10.0)


class ScenarioSwarmAggregate(BaseModel):
    facility_name: str
    scenario_prompt: str
    agents_run: int
    agents_per_role: int
    path_frequency: dict[str, int] = Field(default_factory=dict)
    bottleneck_counts: dict[str, int] = Field(default_factory=dict)
    resource_need_counts: dict[str, int] = Field(default_factory=dict)
    triage_mix: dict[str, int] = Field(default_factory=dict)  # keyed by InjurySeverity
    avg_efficiency: float = 0.0
    efficiency_by_kind: dict[str, float] = Field(default_factory=dict)
    traces: list[ScenarioAgentTrace] = Field(default_factory=list)


class StaffPlacement(BaseModel):
    room_id: str
    kind: ScenarioAgentKind
    count: int = Field(ge=1)
    rationale: str


class ResourceAllocationItem(BaseModel):
    resource: str
    source_room_id: str | None = None
    destination_room_id: str
    quantity: str
    rationale: str


class TriagePriority(BaseModel):
    tier: InjurySeverity
    destination_room_id: str
    routing_rule: str
    staff_required: list[ScenarioAgentKind] = Field(default_factory=list)


class TimelinePhase(BaseModel):
    phase_label: str
    actions: list[str] = Field(default_factory=list)
    decision_points: list[str] = Field(default_factory=list)


class BestPlan(BaseModel):
    staff_placement: list[StaffPlacement] = Field(default_factory=list)
    resource_allocation: list[ResourceAllocationItem] = Field(default_factory=list)
    triage_priorities: list[TriagePriority] = Field(default_factory=list)
    timeline: list[TimelinePhase] = Field(default_factory=list)
    summary: str = ""
    assumptions: list[str] = Field(default_factory=list)


class ScenarioSimulation(BaseModel):
    simulation_id: str
    unit_id: str
    status: SimulationStatus
    scenario_prompt: str
    agents_per_role: int
    triggered_at: datetime
    completed_at: datetime | None = None
    failure_reason: str | None = None
    swarm_aggregate: ScenarioSwarmAggregate | None = None
    best_plan: BestPlan | None = None
