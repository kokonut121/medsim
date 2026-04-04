from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Domain = Literal["ICA", "MSA", "FRA", "ERA", "PFA", "SCA"]
Severity = Literal["CRITICAL", "HIGH", "ADVISORY"]
ModelStatus = Literal["queued", "acquiring", "classifying", "generating", "ready", "failed"]
ScanStatus = Literal["queued", "running", "synthesizing", "complete", "failed"]


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


class GapArea(BaseModel):
    area_id: str
    description: str


class CoverageMap(BaseModel):
    facility_id: str
    covered_areas: list[CoverageArea]
    gap_areas: list[GapArea]


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
    created_at: datetime
    completed_at: datetime | None = None


class FacilityCreate(BaseModel):
    name: str
    address: str

