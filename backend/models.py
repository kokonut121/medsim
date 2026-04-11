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
    model_id: str | None = None
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
    spatial_bundle_json: dict = Field(default_factory=dict)
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
TaskStatus = Literal["queued", "active", "blocked", "complete"]
TaskPriority = Literal["critical", "high", "medium", "low"]
HandoffUrgency = Literal["critical", "high", "medium", "low"]
ChallengeSeverity = Literal["critical", "high", "medium", "low"]
SupervisorInsightKind = Literal["shared_bottleneck", "critical_handoff", "overload", "reroute"]
GraphNodeKind = Literal["agent", "task", "challenge", "role", "insight"]
GraphEdgeKind = Literal["handoff", "owns", "blocked_by", "supports", "highlight"]


class ScenarioTask(BaseModel):
    task_id: str
    label: str
    room_id: str | None = None
    status: TaskStatus = "queued"
    priority: TaskPriority = "medium"


class ScenarioHandoff(BaseModel):
    target_agent_id: str | None = None
    target_kind: ScenarioAgentKind | None = None
    reason: str
    room_id: str | None = None
    urgency: HandoffUrgency = "medium"


class ScenarioChallenge(BaseModel):
    challenge_id: str
    label: str
    room_id: str | None = None
    severity: ChallengeSeverity = "medium"
    impact: str = ""
    blocking: bool = False


class SupervisorInsight(BaseModel):
    insight_id: str
    kind: SupervisorInsightKind
    title: str
    summary: str
    room_id: str | None = None
    source_agent_ids: list[str] = Field(default_factory=list)
    target_agent_ids: list[str] = Field(default_factory=list)
    emphasis: ChallengeSeverity = "medium"


class ScenarioGraphNode(BaseModel):
    id: str
    kind: GraphNodeKind
    label: str
    role_kind: ScenarioAgentKind | None = None
    room_id: str | None = None
    parent_id: str | None = None
    emphasis: str | None = None
    detail: str = ""
    revealed_at_step: int = 0


class ScenarioGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: GraphEdgeKind
    label: str = ""
    urgency: str | None = None
    revealed_at_step: int = 0


class ScenarioGraphSnapshot(BaseModel):
    version: int = 1
    phase: str = "running"
    step: int = 0
    nodes: list[ScenarioGraphNode] = Field(default_factory=list)
    edges: list[ScenarioGraphEdge] = Field(default_factory=list)
    highlighted_node_ids: list[str] = Field(default_factory=list)
    narrative: str = ""


class ScenarioAgentTrace(BaseModel):
    agent_index: int
    agent_id: str = ""
    call_sign: str = ""
    kind: ScenarioAgentKind
    role_label: str
    focus_room_id: str | None = None
    actions: list[str] = Field(default_factory=list)
    path: list[str] = Field(default_factory=list)
    bottlenecks: list[str] = Field(default_factory=list)
    resource_needs: list[str] = Field(default_factory=list)
    patient_tags: list[InjurySeverity] = Field(default_factory=list)
    tasks: list[ScenarioTask] = Field(default_factory=list)
    handoffs: list[ScenarioHandoff] = Field(default_factory=list)
    challenges: list[ScenarioChallenge] = Field(default_factory=list)
    notes: str = ""
    efficiency_score: float = Field(default=5.0, ge=0.0, le=10.0)


ScenarioAgentEventKind = Literal["focus", "task", "handoff", "challenge", "note", "done"]


class ScenarioAgentEvent(BaseModel):
    """One discrete decision streamed by an agent during its NDJSON run.

    The ``kind`` discriminator selects which payload field is meaningful:
    - ``focus``: focus_room_id + path + actions + bottlenecks + resource_needs + patient_tags
    - ``task`` / ``handoff`` / ``challenge``: the matching nested object
    - ``note``: free-text note
    - ``done``: efficiency_score
    """

    agent_id: str
    agent_index: int
    agent_kind: ScenarioAgentKind
    call_sign: str = ""
    role_label: str = ""
    kind: ScenarioAgentEventKind
    seq: int = 0
    # focus payload
    focus_room_id: str | None = None
    path: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    bottlenecks: list[str] = Field(default_factory=list)
    resource_needs: list[str] = Field(default_factory=list)
    patient_tags: list[InjurySeverity] = Field(default_factory=list)
    # task / handoff / challenge payloads
    task: ScenarioTask | None = None
    handoff: ScenarioHandoff | None = None
    challenge: ScenarioChallenge | None = None
    # note payload
    note: str | None = None
    # done payload
    efficiency_score: float | None = None


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


class ScenarioReasonerResult(BaseModel):
    best_plan: BestPlan
    supervisor_insights: list[SupervisorInsight] = Field(default_factory=list)


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
    reasoning_graph: ScenarioGraphSnapshot | None = None
    best_plan: BestPlan | None = None
