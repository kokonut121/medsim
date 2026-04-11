from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from backend.config import Settings, get_settings
from backend.db.fhir_repository import FHIRRepositoryClient
from backend.reports.fhir_projector import build_diagnostic_report, build_observation, fhir_safe_id
from backend.models import CoverageArea, CoverageMap, DomainStatus, Facility, FacilityCreate, Finding, GapArea, ImageMeta, Scan, ScenarioSimulation, SpatialAnchor, Unit, WorldModel


logger = logging.getLogger(__name__)
UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


class MemoryIRISClient:
    """
    Development-safe stand-in for InterSystems IRIS.
    The public interface mirrors the production client so route logic stays stable.
    """

    mode = "memory"

    def __init__(self) -> None:
        self.facilities: dict[str, Facility] = {}
        self.units: dict[str, Unit] = {}
        self.models: dict[str, WorldModel] = {}
        self.scans: dict[str, Scan] = {}
        self.images: dict[str, ImageMeta] = {}
        self.images_by_facility: defaultdict[str, list[str]] = defaultdict(list)
        self.findings_by_scan: defaultdict[str, list[Finding]] = defaultdict(list)
        self.coverage_maps: dict[str, CoverageMap] = {}
        self.upload_sessions: dict[str, dict[str, Any]] = {}
        # In-memory FHIR resource cache: resourceType/id → resource dict
        self._fhir_resources: dict[str, dict[str, Any]] = {}
        self.simulations: dict[str, ScenarioSimulation] = {}
        self.simulations_by_unit: defaultdict[str, list[str]] = defaultdict(list)
        self._seed_demo_data()

    def _seed_demo_data(self) -> None:
        if self.facilities:
            return

        facility_id = "fac_demo"
        created_at = utcnow() - timedelta(days=2)
        facility = Facility(
            facility_id=facility_id,
            name="LeTourneau University — Nursing Skills Lab",
            address="2100 S Mobberly Ave, Longview, TX 75602",
            lat=32.4795,
            lng=-94.7390,
            org_id="org_letu",
            google_place_id="letu-nursing-lab-placeholder",
            osm_building_id="osm-letu-1",
            created_at=created_at,
        )
        self.facilities[facility_id] = facility

        unit_id = "unit_1"
        self.units[unit_id] = Unit(
            unit_id=unit_id,
            facility_id=facility_id,
            name="Nursing Skills Lab",
            floor=1,
            unit_type="skills_lab",
            created_at=created_at,
        )

        scene_graph = {
            "units": [
                {
                    "unit_id": "unit_1",
                    "unit_type": "Nursing Skills Lab",
                    "rooms": [
                        # ── Entry / Reception ──────────────────────────────────
                        {
                            "room_id": "NL-ENTRY",
                            "type": "lobby_main_entrance",
                            "area_sqft_estimate": 200,
                            "equipment": [
                                {"type": "hand_hygiene_dispenser", "position": "entry door right", "accessible": True, "confidence": 0.94},
                            ],
                            "adjacency": ["NL-HALL"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "supplemental",
                            "grid_col": 1, "grid_row": 0,
                        },
                        # ── Main Hallway (3 waypoints for agent patrol) ────────
                        {
                            "room_id": "NL-HALL",
                            "type": "corridor_hallway",
                            "area_sqft_estimate": 600,
                            "equipment": [
                                {"type": "crash_cart", "position": "alcove outside SIM-1", "accessible": True, "confidence": 0.88},
                            ],
                            "adjacency": ["NL-ENTRY", "NL-SIM1", "NL-SIM2", "NL-SIM3", "NL-DEBRIEF", "NL-SKILLS-A", "NL-SKILLS-B", "NL-SUPPLY", "NL-CONTROL"],
                            "sightline_to_nursing_station": True,
                            "image_source_quality": "supplemental",
                            "grid_col": 1, "grid_row": 1,
                        },
                        {
                            "room_id": "NL-HALL-MID",
                            "type": "corridor_hallway",
                            "area_sqft_estimate": 0,
                            "equipment": [],
                            "adjacency": ["NL-HALL"],
                            "sightline_to_nursing_station": True,
                            "image_source_quality": "supplemental",
                            "grid_col": 1, "grid_row": 2,
                        },
                        {
                            "room_id": "NL-HALL-FAR",
                            "type": "corridor_hallway",
                            "area_sqft_estimate": 0,
                            "equipment": [],
                            "adjacency": ["NL-HALL"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "supplemental",
                            "grid_col": 1, "grid_row": 3,
                        },
                        # ── Simulation Bays ────────────────────────────────────
                        {
                            "room_id": "NL-SIM1",
                            "type": "patient_room",
                            "area_sqft_estimate": 320,
                            "equipment": [
                                {"type": "monitor", "position": "wall mount above bed", "accessible": True, "confidence": 0.96},
                                {"type": "iv_pole", "position": "bedside right", "accessible": True, "confidence": 0.93},
                                {"type": "hand_hygiene_dispenser", "position": "door entry", "accessible": True, "confidence": 0.97},
                                {"type": "call_light", "position": "bed rail", "accessible": True, "confidence": 0.91},
                            ],
                            "adjacency": ["NL-HALL"],
                            "sightline_to_nursing_station": True,
                            "image_source_quality": "supplemental",
                            "grid_col": 0, "grid_row": 1,
                        },
                        {
                            "room_id": "NL-SIM2",
                            "type": "patient_room",
                            "area_sqft_estimate": 320,
                            "equipment": [
                                {"type": "monitor", "position": "wall mount above bed", "accessible": True, "confidence": 0.95},
                                {"type": "ventilator", "position": "head of bed", "accessible": True, "confidence": 0.90},
                                {"type": "iv_pole", "position": "bedside left", "accessible": True, "confidence": 0.92},
                                {"type": "hand_hygiene_dispenser", "position": "door entry — low stock", "accessible": False, "confidence": 0.68},
                            ],
                            "adjacency": ["NL-HALL"],
                            "sightline_to_nursing_station": True,
                            "image_source_quality": "supplemental",
                            "grid_col": 0, "grid_row": 2,
                        },
                        {
                            "room_id": "NL-SIM3",
                            "type": "patient_room",
                            "area_sqft_estimate": 320,
                            "equipment": [
                                {"type": "monitor", "position": "ceiling arm", "accessible": True, "confidence": 0.94},
                                {"type": "iv_pole", "position": "bedside right", "accessible": True, "confidence": 0.91},
                                {"type": "hand_hygiene_dispenser", "position": "missing", "accessible": False, "confidence": 0.82},
                                {"type": "call_light", "position": "missing", "accessible": False, "confidence": 0.62},
                            ],
                            "adjacency": ["TC-CORRIDOR"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "places",
                            "grid_col": 0, "grid_row": 3,
                        },
                        # ── Debriefing Room ────────────────────────────────────
                        {
                            "room_id": "NL-DEBRIEF",
                            "type": "nursing_station",
                            "area_sqft_estimate": 280,
                            "equipment": [
                                {"type": "workstation", "position": "instructor desk", "accessible": True, "confidence": 0.95},
                                {"type": "monitor", "position": "wall display", "accessible": True, "confidence": 0.93},
                            ],
                            "adjacency": ["NL-HALL"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "supplemental",
                            "grid_col": 1, "grid_row": 4,
                        },
                        # ── Skills Station A ───────────────────────────────────
                        {
                            "room_id": "NL-SKILLS-A",
                            "type": "patient_room",
                            "area_sqft_estimate": 250,
                            "equipment": [
                                {"type": "iv_pole", "position": "task trainer station", "accessible": True, "confidence": 0.90},
                                {"type": "hand_hygiene_dispenser", "position": "counter left", "accessible": True, "confidence": 0.92},
                            ],
                            "adjacency": ["NL-HALL"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "supplemental",
                            "grid_col": 0, "grid_row": 0,
                        },
                        # ── Skills Station B ───────────────────────────────────
                        {
                            "room_id": "NL-SKILLS-B",
                            "type": "patient_room",
                            "area_sqft_estimate": 250,
                            "equipment": [
                                {"type": "monitor", "position": "task trainer station", "accessible": True, "confidence": 0.89},
                                {"type": "hand_hygiene_dispenser", "position": "counter right — empty", "accessible": False, "confidence": 0.74},
                            ],
                            "adjacency": ["NL-HALL"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "supplemental",
                            "grid_col": 0, "grid_row": 4,
                        },
                        # ── Supply / Medication Room ───────────────────────────
                        {
                            "room_id": "NL-SUPPLY",
                            "type": "medication_room_pharmacy",
                            "area_sqft_estimate": 160,
                            "equipment": [
                                {"type": "adc", "position": "back wall", "accessible": True, "confidence": 0.94},
                                {"type": "hand_hygiene_dispenser", "position": "door entry", "accessible": True, "confidence": 0.91},
                            ],
                            "adjacency": ["NL-HALL"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "supplemental",
                            "grid_col": 1, "grid_row": 2,
                        },
                        # ── Control / Faculty Room ─────────────────────────────
                        {
                            "room_id": "NL-CONTROL",
                            "type": "utility_support",
                            "area_sqft_estimate": 140,
                            "equipment": [
                                {"type": "workstation", "position": "AV control desk — 2 terminals", "accessible": True, "confidence": 0.96},
                                {"type": "monitor", "position": "sim bay observation screens", "accessible": True, "confidence": 0.95},
                            ],
                            "adjacency": ["NL-HALL"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "supplemental",
                            "grid_col": 1, "grid_row": 3,
                        },
                    ],
                }
            ],
            "flow_annotations": {
                "patient_flow_paths": [["NL-ENTRY", "NL-HALL", "NL-SIM1"]],
                "staff_flow_paths": [["NL-CONTROL", "NL-HALL", "NL-SUPPLY"]],
                "clean_corridors": ["NL-HALL"],
                "dirty_corridors": ["NL-SUPPLY"],
            },
        }
        from backend.pipeline.spatial_bundle import build_spatial_bundle  # noqa: PLC0415
        spatial_bundle = build_spatial_bundle(scene_graph)
        self.models["model_unit_1"] = WorldModel(
            model_id="model_unit_1",
            unit_id="unit_1",
            status="ready",
            splat_r2_key="facilities/fac_demo/models/a97601cc-31b4-418f-a247-35ac9c9b8cb0/scene.spz",
            scene_graph_json=scene_graph,
            world_labs_world_id="a97601cc-31b4-418f-a247-35ac9c9b8cb0",
            world_marble_url="https://marble.worldlabs.ai/world/a97601cc-31b4-418f-a247-35ac9c9b8cb0",
            caption="LeTourneau University — Nursing Skills Lab world model",
            source_image_count=0,
            spatial_bundle_json=spatial_bundle,
            created_at=created_at,
            completed_at=created_at + timedelta(hours=1),
        )

        self.coverage_maps[facility_id] = CoverageMap(
            facility_id=facility_id,
            covered_areas=[],
            gap_areas=[
                GapArea(area_id="sim_bays", description="Simulation bay interior imagery needed"),
                GapArea(area_id="hallway", description="Lab hallway not yet captured"),
            ],
            updated_at=created_at,
        )

        # ── Seeded scan with calibrated spatial anchors ───────────────────────
        # Grid: SCALE=3.5, COL_ORIGIN=0.86, ROW_ORIGIN=0.5
        # Ground plane Y=1.467; heights: dispenser=0.15, cart=0.48, iv=-0.07,
        # workstation=0.37, call_light=0.54, adc=0.21
        scan_id = "scan_demo_001"
        scan_created = utcnow()  # seed as current time so it stays the "latest" scan
        demo_scan = Scan(
            scan_id=scan_id,
            unit_id="unit_1",
            model_id="model_unit_1",
            status="complete",
            findings=[],
            domain_statuses={
                d: DomainStatus(status="completed", finding_count=0,
                                started_at=scan_created, completed_at=scan_created + timedelta(minutes=3))
                for d in ["ICA", "ERA", "MSA", "FRA", "SCA", "PFA"]
            },
            triggered_at=scan_created,
            completed_at=scan_created + timedelta(minutes=5),
        )
        self.scans[scan_id] = demo_scan

        _findings = [
            # ICA — Infection Control
            Finding(
                finding_id="f_ica_01", scan_id=scan_id, domain="ICA", sub_agent="ICA-1",
                room_id="NL-ENTRY", severity="HIGH", compound_severity=0.78,
                label_text="Hand hygiene dispenser empty at entry",
                spatial_anchor=SpatialAnchor(x=0.49, y=0.15, z=-1.75),
                confidence=0.94, evidence_r2_keys=[],
                recommendation="Refill dispenser immediately; add secondary unit at door frame.",
                compound_domains=["ICA"], created_at=scan_created,
            ),
            Finding(
                finding_id="f_ica_02", scan_id=scan_id, domain="ICA", sub_agent="ICA-2",
                room_id="NL-SIM3", severity="CRITICAL", compound_severity=0.91,
                label_text="Hand hygiene dispenser missing — SIM Bay 3 entry",
                spatial_anchor=SpatialAnchor(x=-3.01, y=0.15, z=8.75),
                confidence=0.89, evidence_r2_keys=[],
                recommendation="Mount standard wall dispenser at door entry per HAI protocol.",
                compound_domains=["ICA"], created_at=scan_created,
            ),
            Finding(
                finding_id="f_ica_03", scan_id=scan_id, domain="ICA", sub_agent="ICA-1",
                room_id="NL-SKILLS-A", severity="HIGH", compound_severity=0.74,
                label_text="Dispenser low-stock at Skills Station A",
                spatial_anchor=SpatialAnchor(x=-3.01, y=0.15, z=-1.75),
                confidence=0.92, evidence_r2_keys=[],
                recommendation="Replace cartridge; schedule daily stock checks.",
                compound_domains=["ICA"], created_at=scan_created,
            ),
            # ERA — Emergency Response
            Finding(
                finding_id="f_era_01", scan_id=scan_id, domain="ERA", sub_agent="ERA-1",
                room_id="NL-HALL", severity="HIGH", compound_severity=0.82,
                label_text="Crash cart access path partially obstructed",
                spatial_anchor=SpatialAnchor(x=0.49, y=0.48, z=1.75),
                confidence=0.88, evidence_r2_keys=[],
                recommendation="Clear 1.5m radius around crash cart at all times per code blue protocol.",
                compound_domains=["ERA", "PFA"], created_at=scan_created,
            ),
            Finding(
                finding_id="f_era_02", scan_id=scan_id, domain="ERA", sub_agent="ERA-1",
                room_id="NL-CONTROL", severity="ADVISORY", compound_severity=0.52,
                label_text="AED not visible from main corridor",
                spatial_anchor=SpatialAnchor(x=0.49, y=0.37, z=8.75),
                confidence=0.81, evidence_r2_keys=[],
                recommendation="Install directional AED signage in hallway; verify monthly placement.",
                compound_domains=["ERA"], created_at=scan_created,
            ),
            # MSA — Medication Safety
            Finding(
                finding_id="f_msa_01", scan_id=scan_id, domain="MSA", sub_agent="MSA-1",
                room_id="NL-SUPPLY", severity="CRITICAL", compound_severity=0.93,
                label_text="ADC medication drawer left unlocked — unattended",
                spatial_anchor=SpatialAnchor(x=0.49, y=0.21, z=5.25),
                confidence=0.94, evidence_r2_keys=[],
                recommendation="Lock ADC on exit; enable auto-lock after 30 s inactivity.",
                compound_domains=["MSA"], created_at=scan_created,
            ),
            # FRA — Fall Risk
            Finding(
                finding_id="f_fra_01", scan_id=scan_id, domain="FRA", sub_agent="FRA-1",
                room_id="NL-SIM2", severity="HIGH", compound_severity=0.76,
                label_text="IV pole positioned at walking edge — fall hazard",
                spatial_anchor=SpatialAnchor(x=-3.01, y=-0.07, z=5.25),
                confidence=0.91, evidence_r2_keys=[],
                recommendation="Reposition IV pole to bedside; secure base lock when stationary.",
                compound_domains=["FRA"], created_at=scan_created,
            ),
            Finding(
                finding_id="f_fra_02", scan_id=scan_id, domain="FRA", sub_agent="FRA-1",
                room_id="NL-SIM3", severity="ADVISORY", compound_severity=0.55,
                label_text="Call light not within patient reach",
                spatial_anchor=SpatialAnchor(x=-3.01, y=0.54, z=9.0),
                confidence=0.82, evidence_r2_keys=[],
                recommendation="Attach call light to bed rail within arm's reach of patient.",
                compound_domains=["FRA", "SCA"], created_at=scan_created,
            ),
            # SCA — Safe Communication
            Finding(
                finding_id="f_sca_01", scan_id=scan_id, domain="SCA", sub_agent="SCA-1",
                room_id="NL-SIM2", severity="ADVISORY", compound_severity=0.48,
                label_text="Patient name visible on whiteboard from corridor",
                spatial_anchor=SpatialAnchor(x=-3.01, y=0.37, z=5.0),
                confidence=0.85, evidence_r2_keys=[],
                recommendation="Reposition whiteboard or install privacy screen at doorway.",
                compound_domains=["SCA"], created_at=scan_created,
            ),
            # PFA — Patient Flow
            Finding(
                finding_id="f_pfa_01", scan_id=scan_id, domain="PFA", sub_agent="PFA-1",
                room_id="NL-HALL-MID", severity="ADVISORY", compound_severity=0.51,
                label_text="Corridor width reduced near SIM-2 junction",
                spatial_anchor=SpatialAnchor(x=0.49, y=0.48, z=5.25),
                confidence=0.79, evidence_r2_keys=[],
                recommendation="Remove non-essential equipment from corridor to maintain 1.8m clear width.",
                compound_domains=["PFA", "ERA"], created_at=scan_created,
            ),
        ]
        self.write_findings(demo_scan, _findings)

    def list_facilities(self) -> list[Facility]:
        return list(self.facilities.values())

    def create_facility(self, payload: FacilityCreate) -> Facility:
        facility_id = f"fac_{uuid4().hex[:8]}"
        created = Facility(
            facility_id=facility_id,
            name=payload.name,
            address=payload.address,
            lat=getattr(payload, "lat", None) or 41.881,
            lng=getattr(payload, "lng", None) or -87.623,
            org_id="org_demo",
            google_place_id=getattr(payload, "google_place_id", None) or f"place_{facility_id}",
            osm_building_id=getattr(payload, "osm_building_id", None) or f"osm_{facility_id}",
            created_at=utcnow(),
        )
        self.facilities[facility_id] = created
        unit_id = f"{facility_id}_unit_1"
        self.units[unit_id] = Unit(
            unit_id=unit_id,
            facility_id=facility_id,
            name=payload.unit_name or "Trauma Center",
            floor=payload.floor,
            unit_type=payload.unit_type or "Trauma",
            created_at=utcnow(),
        )
        self.coverage_maps[facility_id] = CoverageMap(
            facility_id=facility_id,
            covered_areas=[],
            gap_areas=[GapArea(area_id="facility_pending", description="Imagery acquisition not started")],
            updated_at=utcnow(),
        )
        return created

    def get_facility(self, facility_id: str) -> dict[str, Any]:
        facility = self.facilities[facility_id]
        units = [unit for unit in self.units.values() if unit.facility_id == facility_id]
        models = sorted(
            [model for model in self.models.values() if model.unit_id in {unit.unit_id for unit in units}],
            key=lambda model: model.created_at,
            reverse=True,
        )
        return {"facility": facility, "units": units, "models": models}

    def delete_facility(self, facility_id: str) -> None:
        self.facilities.pop(facility_id, None)
        doomed_units = [unit_id for unit_id, unit in self.units.items() if unit.facility_id == facility_id]
        for unit_id in doomed_units:
            self.units.pop(unit_id, None)
        doomed_models = [model_id for model_id, model in self.models.items() if model.unit_id in doomed_units]
        for model_id in doomed_models:
            self.models.pop(model_id, None)
        doomed_images = self.images_by_facility.pop(facility_id, [])
        for image_id in doomed_images:
            self.images.pop(image_id, None)
        self.coverage_maps.pop(facility_id, None)

    def get_coverage(self, facility_id: str) -> CoverageMap:
        return self.coverage_maps[facility_id]

    def get_unit_for_facility(self, facility_id: str) -> Unit:
        return next(unit for unit in self.units.values() if unit.facility_id == facility_id)

    def create_or_replace_model(self, facility_id: str, *, status: str = "queued") -> WorldModel:
        unit = self.get_unit_for_facility(facility_id)
        model = WorldModel(
            model_id=f"model_{uuid4().hex[:8]}",
            unit_id=unit.unit_id,
            status=status,
            splat_r2_key="",
            scene_graph_json={},
            world_labs_world_id="",
            created_at=utcnow(),
        )
        self.models[model.model_id] = model
        return model

    def update_model(
        self,
        model_id: str,
        *,
        status: str | None = None,
        splat_r2_key: str | None = None,
        scene_graph_json: dict | None = None,
        world_labs_world_id: str | None = None,
        source_image_count: int | None = None,
        failure_reason: str | None = None,
        caption: str | None = None,
        thumbnail_url: str | None = None,
        world_marble_url: str | None = None,
        completed_at: datetime | None = None,
    ) -> WorldModel:
        model = self.models[model_id]
        updates = model.model_dump()
        if status is not None:
            updates["status"] = status
        if splat_r2_key is not None:
            updates["splat_r2_key"] = splat_r2_key
        if scene_graph_json is not None:
            updates["scene_graph_json"] = scene_graph_json
        if world_labs_world_id is not None:
            updates["world_labs_world_id"] = world_labs_world_id
        if source_image_count is not None:
            updates["source_image_count"] = source_image_count
        if failure_reason is not None:
            updates["failure_reason"] = failure_reason
        if caption is not None:
            updates["caption"] = caption
        if thumbnail_url is not None:
            updates["thumbnail_url"] = thumbnail_url
        if world_marble_url is not None:
            updates["world_marble_url"] = world_marble_url
        if completed_at is not None:
            updates["completed_at"] = completed_at
        self.models[model_id] = WorldModel.model_validate(updates)
        return self.models[model_id]

    def write_world_model(self, facility_id: str, world_model: dict[str, Any], model_id: str | None = None) -> WorldModel:
        unit = next(unit for unit in self.units.values() if unit.facility_id == facility_id)
        model = self.models.get(model_id) if model_id else None
        created_at = model.created_at if model else utcnow()
        ready_model = WorldModel(
            model_id=model.model_id if model else f"model_{uuid4().hex[:8]}",
            unit_id=unit.unit_id,
            status="ready",
            splat_r2_key=world_model["splat_url"],
            scene_graph_json=world_model["scene_manifest"],
            world_labs_world_id=world_model["world_id"],
            source_image_count=world_model.get("source_image_count", 0),
            caption=world_model.get("caption"),
            thumbnail_url=world_model.get("thumbnail_url"),
            world_marble_url=world_model.get("world_marble_url"),
            created_at=created_at,
            completed_at=utcnow(),
        )
        self.models[ready_model.model_id] = ready_model
        return ready_model

    def write_image_meta(self, image_meta: ImageMeta) -> ImageMeta:
        self.images[image_meta.image_id] = image_meta
        self.images_by_facility[image_meta.facility_id].append(image_meta.image_id)
        return image_meta

    def update_image_classification(self, image_id: str, *, category: str, confidence: float, notes: str | None = None) -> ImageMeta:
        image = self.images[image_id]
        updates = image.model_dump()
        updates["category"] = category
        updates["confidence"] = confidence
        updates["notes"] = notes
        self.images[image_id] = ImageMeta.model_validate(updates)
        return self.images[image_id]

    def list_images_for_facility(self, facility_id: str) -> list[ImageMeta]:
        return [self.images[image_id] for image_id in self.images_by_facility.get(facility_id, [])]

    def update_coverage(self, facility_id: str, covered_areas: list[CoverageArea], gap_areas: list[GapArea]) -> CoverageMap:
        coverage = CoverageMap(
            facility_id=facility_id,
            covered_areas=covered_areas,
            gap_areas=gap_areas,
            updated_at=utcnow(),
        )
        self.coverage_maps[facility_id] = coverage
        return coverage

    def create_upload_session(self, upload_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.upload_sessions[upload_id] = payload
        return self.upload_sessions[upload_id]

    def get_upload_session(self, upload_id: str) -> dict[str, Any]:
        return self.upload_sessions[upload_id]

    def update_upload_session(self, upload_id: str, **updates: object) -> dict[str, Any]:
        session = self.upload_sessions[upload_id]
        session.update(updates)
        return session

    def write_scan(self, scan: Scan) -> Scan:
        """Persist a Scan record (may be queued/running, no findings yet)."""
        self.scans[scan.scan_id] = scan
        return scan

    def get_scan(self, scan_id: str) -> Scan:
        if scan_id not in self.scans:
            raise KeyError(scan_id)
        return self.scans[scan_id]

    def update_scan_status(self, scan_id: str, status: str) -> Scan | None:
        scan = self.scans.get(scan_id)
        if scan is None:
            return None
        updates = scan.model_dump()
        updates["status"] = status
        updated = Scan.model_validate(updates)
        self.scans[scan_id] = updated
        return updated

    def write_findings(self, scan: Scan, findings: list[Finding]) -> Scan:
        scan.findings = findings
        self.findings_by_scan[scan.scan_id] = findings
        self.scans[scan.scan_id] = scan
        # Cache FHIR projections so get_*_resource returns stable resources
        for finding in findings:
            obs = build_observation(finding)
            self._fhir_resources[f"Observation/{finding.finding_id}"] = obs
            self._fhir_resources[f"Observation/{obs['id']}"] = obs
        report = build_diagnostic_report(scan)
        self._fhir_resources[f"DiagnosticReport/{scan.scan_id}"] = report
        self._fhir_resources[f"DiagnosticReport/{report['id']}"] = report
        return scan

    def list_findings(self, unit_id: str, domain: str | None = None, severity: str | None = None, room_id: str | None = None) -> list[Finding]:
        scans = [scan for scan in self.scans.values() if scan.unit_id == unit_id]
        # Only use the most recent complete scan to avoid mixing stale data
        complete_scans = sorted(
            [s for s in scans if s.status == "complete"],
            key=lambda s: s.triggered_at,
            reverse=True,
        )
        source_scans = complete_scans[:1] if complete_scans else scans
        findings = [finding for scan in source_scans for finding in scan.findings]
        if domain:
            findings = [finding for finding in findings if finding.domain == domain]
        if severity:
            findings = [finding for finding in findings if finding.severity == severity]
        if room_id:
            findings = [finding for finding in findings if finding.room_id == room_id]
        return findings

    def get_finding(self, finding_id: str) -> Finding:
        for findings in self.findings_by_scan.values():
            for finding in findings:
                if finding.finding_id == finding_id or fhir_safe_id(finding.finding_id) == finding_id:
                    return finding
        raise KeyError(finding_id)

    def list_models(self, unit_id: str) -> list[WorldModel]:
        return [model for model in self.models.values() if model.unit_id == unit_id]

    def get_model(self, unit_id: str) -> WorldModel:
        models = self.list_models(unit_id)
        if not models:
            raise KeyError(unit_id)
        return sorted(models, key=lambda item: item.created_at)[-1]

    # ----- Scenario simulation persistence -------------------------------

    def write_simulation(self, sim: ScenarioSimulation) -> ScenarioSimulation:
        self.simulations[sim.simulation_id] = sim
        if sim.simulation_id not in self.simulations_by_unit[sim.unit_id]:
            self.simulations_by_unit[sim.unit_id].append(sim.simulation_id)
        return sim

    def update_simulation(self, simulation_id: str, **updates: object) -> ScenarioSimulation:
        sim = self.simulations[simulation_id]
        data = sim.model_dump()
        for key, value in updates.items():
            data[key] = value
        updated = ScenarioSimulation.model_validate(data)
        self.simulations[simulation_id] = updated
        return updated

    def get_simulation(self, simulation_id: str) -> ScenarioSimulation:
        return self.simulations[simulation_id]

    def list_simulations(self, unit_id: str) -> list[ScenarioSimulation]:
        ids = self.simulations_by_unit.get(unit_id, [])
        sims = [self.simulations[sid] for sid in ids if sid in self.simulations]
        return sorted(sims, key=lambda item: item.triggered_at, reverse=True)

    def get_latest_simulation(self, unit_id: str) -> ScenarioSimulation:
        sims = self.list_simulations(unit_id)
        if not sims:
            raise KeyError(unit_id)
        return sims[0]

    def get_diagnostic_report_resource(self, scan_id: str) -> dict[str, Any]:
        cached = self._fhir_resources.get(f"DiagnosticReport/{scan_id}")
        if cached:
            return cached
        scan = self.scans.get(scan_id)
        if not scan:
            scan = next((item for item in self.scans.values() if fhir_safe_id(item.scan_id) == scan_id), None)
        if scan is None:
            raise KeyError(scan_id)
        return build_diagnostic_report(scan)

    def get_observation_resource(self, finding_id: str) -> dict[str, Any]:
        cached = self._fhir_resources.get(f"Observation/{finding_id}")
        if cached:
            return cached
        return build_observation(self.get_finding(finding_id))

    def push_diagnostic_report(self, scan_id: str, target: str | None = None) -> dict[str, Any]:
        settings = get_settings()
        destination = (target or settings.iris_health_connect_endpoint or "").rstrip("/")
        if not destination:
            return {"status": "not_configured", "target": target, "scan_id": scan_id}
        report = self.get_diagnostic_report_resource(scan_id)
        observations: list[dict[str, Any]] = []
        for ref in report.get("result", []):
            ref_id = ref.get("reference", "").split("/", 1)[-1]
            if ref_id:
                observations.append(self.get_observation_resource(ref_id))
        fhir_client = FHIRRepositoryClient(
            base_url=destination,
            username=settings.iris_user,
            password=settings.iris_password,
        )
        return fhir_client.push_bundle([*observations, report], target_base=destination)


class FHIRServiceIRISClient(MemoryIRISClient):
    """
    FHIR-only mode: keep MedSim domain data in the in-memory dev store,
    but use the live IRIS FHIR repository for interoperability reads/writes
    whenever it is available.
    """

    mode = "fhir"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._fhir_repository = FHIRRepositoryClient(
            base_url=settings.iris_fhir_base,
            username=settings.iris_user,
            password=settings.iris_password,
        )
        super().__init__()

    def write_findings(self, scan: Scan, findings: list[Finding]) -> Scan:
        stored_scan = super().write_findings(scan, findings)
        try:
            for finding in findings:
                self._fhir_repository.put_resource(build_observation(finding))
            self._fhir_repository.put_resource(build_diagnostic_report(stored_scan))
        except Exception:
            logger.exception("Failed to project scan %s into the live IRIS FHIR repository", scan.scan_id)
        return stored_scan

    def get_diagnostic_report_resource(self, scan_id: str) -> dict[str, Any]:
        try:
            resource = self._fhir_repository.get_resource("DiagnosticReport", fhir_safe_id(scan_id))
            if resource is not None:
                return resource
        except Exception:
            logger.exception("Failed to fetch DiagnosticReport/%s from the live IRIS FHIR repository", scan_id)
        return super().get_diagnostic_report_resource(scan_id)

    def get_observation_resource(self, finding_id: str) -> dict[str, Any]:
        try:
            resource = self._fhir_repository.get_resource("Observation", fhir_safe_id(finding_id))
            if resource is not None:
                return resource
        except Exception:
            logger.exception("Failed to fetch Observation/%s from the live IRIS FHIR repository", finding_id)
        return super().get_observation_resource(finding_id)


class NativeIRISClient:
    mode = "native"

    def __init__(self, settings: Settings) -> None:
        try:
            import iris
        except ImportError as exc:
            raise RuntimeError(
                "InterSystems native mode requires the 'intersystems-irispython' package. "
                "Install backend dependencies before setting MEDSIM_IRIS_MODE=native."
            ) from exc

        self._settings = settings
        self._iris_module = iris
        self._connection = iris.connect(
            hostname=settings.iris_host,
            port=settings.iris_port,
            namespace=settings.iris_namespace,
            username=settings.iris_user,
            password=settings.iris_password,
            timeout=settings.iris_connect_timeout_ms,
            sharedmemory=settings.iris_sharedmemory,
        )
        self._iris = iris.createIRIS(self._connection)
        self._verify_native_global_access()
        self._fhir_repository = FHIRRepositoryClient(
            base_url=settings.iris_fhir_base,
            username=settings.iris_user,
            password=settings.iris_password,
        )
        self.upload_sessions: dict[str, dict[str, Any]] = {}
        self._seed_demo_data()

    def _verify_native_global_access(self) -> None:
        try:
            self._iris.node("^MedSim.Bootstrap").get("namespace", None)
        except RuntimeError as exc:
            if "%Native_GlobalAccess" not in str(exc):
                raise
            raise RuntimeError(
                "IRIS native mode connected successfully, but the configured service account lacks the "
                "%Native_GlobalAccess resource. Re-run the MedSim IRIS bootstrap so the service role "
                "is granted native global access."
            ) from exc

    @property
    def facilities(self) -> dict[str, Facility]:
        return self._load_models("MedSim.Facility", Facility)

    @property
    def units(self) -> dict[str, Unit]:
        return self._load_models("MedSim.Unit", Unit)

    @property
    def models(self) -> dict[str, WorldModel]:
        return self._load_models("MedSim.WorldModel", WorldModel)

    @property
    def scans(self) -> dict[str, Scan]:
        return self._load_models("MedSim.Scan", Scan)

    @property
    def images(self) -> dict[str, ImageMeta]:
        return self._load_models("MedSim.ImageMeta", ImageMeta)

    @property
    def coverage_maps(self) -> dict[str, CoverageMap]:
        return self._load_models("MedSim.CoverageMap", CoverageMap)

    @property
    def simulations(self) -> dict[str, ScenarioSimulation]:
        return self._load_models("MedSim.ScenarioSimulation", ScenarioSimulation)

    @property
    def findings_by_scan(self) -> defaultdict[str, list[Finding]]:
        grouped: defaultdict[str, list[Finding]] = defaultdict(list)
        for finding in self._load_models("MedSim.Finding", Finding).values():
            grouped[finding.scan_id].append(finding)
        return grouped

    @property
    def simulations_by_unit(self) -> defaultdict[str, list[str]]:
        grouped: defaultdict[str, list[str]] = defaultdict(list)
        for simulation_id, simulation in self.simulations.items():
            grouped[simulation.unit_id].append(simulation_id)
        return grouped

    @property
    def images_by_facility(self) -> defaultdict[str, list[str]]:
        grouped: defaultdict[str, list[str]] = defaultdict(list)
        for image_id, image in self.images.items():
            grouped[image.facility_id].append(image_id)
        return grouped

    def _seed_demo_data(self) -> None:
        if self.facilities:
            return
        # Reuse the same seed data shape as memory mode.
        memory = MemoryIRISClient()
        for facility in memory.facilities.values():
            self._store_model("MedSim.Facility", facility.facility_id, facility)
        for unit in memory.units.values():
            self._store_model("MedSim.Unit", unit.unit_id, unit)
        for model in memory.models.values():
            self._store_model("MedSim.WorldModel", model.model_id, model)
        for coverage in memory.coverage_maps.values():
            self._store_model("MedSim.CoverageMap", coverage.facility_id, coverage)

    def _store_json(self, global_name: str, record_id: str, payload: dict[str, Any]) -> None:
        self._iris.node(global_name)[record_id] = json.dumps(payload)

    def _load_json(self, global_name: str, record_id: str) -> dict[str, Any] | None:
        raw = self._iris.node(global_name).get(record_id, None)
        if raw is None:
            return None
        return json.loads(raw)

    def _store_model(self, global_name: str, record_id: str, model: Any) -> Any:
        payload = model.model_dump(mode="json") if hasattr(model, "model_dump") else model
        self._store_json(global_name, record_id, payload)
        return model

    def _load_models(self, global_name: str, model_cls: Any) -> dict[str, Any]:
        node = self._iris.node(global_name)
        records: dict[str, Any] = {}
        for record_id, payload in node.items():
            if payload is None:
                continue
            records[str(record_id)] = model_cls.model_validate(json.loads(payload))
        return records

    def _delete_record(self, global_name: str, record_id: str) -> None:
        self._iris.kill(global_name, record_id)

    def list_facilities(self) -> list[Facility]:
        return list(self.facilities.values())

    def create_facility(self, payload: FacilityCreate) -> Facility:
        facility_id = f"fac_{uuid4().hex[:8]}"
        created = Facility(
            facility_id=facility_id,
            name=payload.name,
            address=payload.address,
            lat=getattr(payload, "lat", None) or 41.881,
            lng=getattr(payload, "lng", None) or -87.623,
            org_id="org_demo",
            google_place_id=getattr(payload, "google_place_id", None) or f"place_{facility_id}",
            osm_building_id=getattr(payload, "osm_building_id", None) or f"osm_{facility_id}",
            created_at=utcnow(),
        )
        self._store_model("MedSim.Facility", facility_id, created)

        unit = Unit(
            unit_id=f"{facility_id}_unit_1",
            facility_id=facility_id,
            name=payload.unit_name or "Trauma Center",
            floor=payload.floor,
            unit_type=payload.unit_type or "Trauma",
            created_at=utcnow(),
        )
        self._store_model("MedSim.Unit", unit.unit_id, unit)

        coverage = CoverageMap(
            facility_id=facility_id,
            covered_areas=[],
            gap_areas=[GapArea(area_id="facility_pending", description="Imagery acquisition not started")],
            updated_at=utcnow(),
        )
        self._store_model("MedSim.CoverageMap", facility_id, coverage)
        return created

    def get_facility(self, facility_id: str) -> dict[str, Any]:
        facility = self.facilities[facility_id]
        units = [unit for unit in self.units.values() if unit.facility_id == facility_id]
        models = sorted(
            [model for model in self.models.values() if model.unit_id in {unit.unit_id for unit in units}],
            key=lambda model: model.created_at,
            reverse=True,
        )
        return {"facility": facility, "units": units, "models": models}

    def delete_facility(self, facility_id: str) -> None:
        doomed_units = [unit_id for unit_id, unit in self.units.items() if unit.facility_id == facility_id]
        doomed_models = [model_id for model_id, model in self.models.items() if model.unit_id in doomed_units]
        doomed_images = [image_id for image_id, image in self.images.items() if image.facility_id == facility_id]
        for unit_id in doomed_units:
            self._delete_record("MedSim.Unit", unit_id)
        for model_id in doomed_models:
            self._delete_record("MedSim.WorldModel", model_id)
        for image_id in doomed_images:
            self._delete_record("MedSim.ImageMeta", image_id)
        for scan_id, scan in self.scans.items():
            if scan.unit_id in doomed_units:
                for finding in scan.findings:
                    self._delete_record("MedSim.Finding", finding.finding_id)
                self._delete_record("MedSim.Scan", scan_id)
        self._delete_record("MedSim.CoverageMap", facility_id)
        self._delete_record("MedSim.Facility", facility_id)

    def get_coverage(self, facility_id: str) -> CoverageMap:
        return self.coverage_maps[facility_id]

    def get_unit_for_facility(self, facility_id: str) -> Unit:
        return next(unit for unit in self.units.values() if unit.facility_id == facility_id)

    def create_or_replace_model(self, facility_id: str, *, status: str = "queued") -> WorldModel:
        unit = self.get_unit_for_facility(facility_id)
        model = WorldModel(
            model_id=f"model_{uuid4().hex[:8]}",
            unit_id=unit.unit_id,
            status=status,
            splat_r2_key="",
            scene_graph_json={},
            world_labs_world_id="",
            created_at=utcnow(),
        )
        return self._store_model("MedSim.WorldModel", model.model_id, model)

    def update_model(
        self,
        model_id: str,
        *,
        status: str | None = None,
        splat_r2_key: str | None = None,
        scene_graph_json: dict | None = None,
        world_labs_world_id: str | None = None,
        source_image_count: int | None = None,
        failure_reason: str | None = None,
        caption: str | None = None,
        thumbnail_url: str | None = None,
        world_marble_url: str | None = None,
        spatial_bundle_json: dict | None = None,
        completed_at: datetime | None = None,
    ) -> WorldModel:
        model = self.models[model_id]
        updates = model.model_dump()
        if status is not None:
            updates["status"] = status
        if splat_r2_key is not None:
            updates["splat_r2_key"] = splat_r2_key
        if scene_graph_json is not None:
            updates["scene_graph_json"] = scene_graph_json
        if world_labs_world_id is not None:
            updates["world_labs_world_id"] = world_labs_world_id
        if source_image_count is not None:
            updates["source_image_count"] = source_image_count
        if failure_reason is not None:
            updates["failure_reason"] = failure_reason
        if caption is not None:
            updates["caption"] = caption
        if thumbnail_url is not None:
            updates["thumbnail_url"] = thumbnail_url
        if world_marble_url is not None:
            updates["world_marble_url"] = world_marble_url
        if spatial_bundle_json is not None:
            updates["spatial_bundle_json"] = spatial_bundle_json
        if completed_at is not None:
            updates["completed_at"] = completed_at
        updated = WorldModel.model_validate(updates)
        return self._store_model("MedSim.WorldModel", model_id, updated)

    def write_world_model(self, facility_id: str, world_model: dict[str, Any], model_id: str | None = None) -> WorldModel:
        unit = self.get_unit_for_facility(facility_id)
        model = self.models.get(model_id) if model_id else None
        created_at = model.created_at if model else utcnow()
        ready_model = WorldModel(
            model_id=model.model_id if model else f"model_{uuid4().hex[:8]}",
            unit_id=unit.unit_id,
            status="ready",
            splat_r2_key=world_model["splat_url"],
            scene_graph_json=world_model["scene_manifest"],
            world_labs_world_id=world_model["world_id"],
            source_image_count=world_model.get("source_image_count", 0),
            caption=world_model.get("caption"),
            thumbnail_url=world_model.get("thumbnail_url"),
            world_marble_url=world_model.get("world_marble_url"),
            created_at=created_at,
            completed_at=utcnow(),
        )
        return self._store_model("MedSim.WorldModel", ready_model.model_id, ready_model)

    def write_image_meta(self, image_meta: ImageMeta) -> ImageMeta:
        return self._store_model("MedSim.ImageMeta", image_meta.image_id, image_meta)

    def update_image_classification(self, image_id: str, *, category: str, confidence: float, notes: str | None = None) -> ImageMeta:
        image = self.images[image_id]
        updates = image.model_dump()
        updates["category"] = category
        updates["confidence"] = confidence
        updates["notes"] = notes
        updated = ImageMeta.model_validate(updates)
        return self._store_model("MedSim.ImageMeta", image_id, updated)

    def list_images_for_facility(self, facility_id: str) -> list[ImageMeta]:
        return [image for image in self.images.values() if image.facility_id == facility_id]

    def update_coverage(self, facility_id: str, covered_areas: list[CoverageArea], gap_areas: list[GapArea]) -> CoverageMap:
        coverage = CoverageMap(
            facility_id=facility_id,
            covered_areas=covered_areas,
            gap_areas=gap_areas,
            updated_at=utcnow(),
        )
        return self._store_model("MedSim.CoverageMap", facility_id, coverage)

    def create_upload_session(self, upload_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.upload_sessions[upload_id] = payload
        return self.upload_sessions[upload_id]

    def get_upload_session(self, upload_id: str) -> dict[str, Any]:
        return self.upload_sessions[upload_id]

    def update_upload_session(self, upload_id: str, **updates: object) -> dict[str, Any]:
        session = self.upload_sessions[upload_id]
        session.update(updates)
        return session

    def write_scan(self, scan: Scan) -> Scan:
        return self._store_model("MedSim.Scan", scan.scan_id, scan)

    def get_scan(self, scan_id: str) -> Scan:
        scan = self._load_json("MedSim.Scan", scan_id)
        if scan is None:
            raise KeyError(scan_id)
        return Scan.model_validate(scan)

    def update_scan_status(self, scan_id: str, status: str) -> Scan | None:
        scan = self._load_json("MedSim.Scan", scan_id)
        if scan is None:
            return None
        scan["status"] = status
        updated = Scan.model_validate(scan)
        return self._store_model("MedSim.Scan", scan_id, updated)

    def write_findings(self, scan: Scan, findings: list[Finding]) -> Scan:
        stored_scan = scan.model_copy(update={"findings": findings})
        for finding in findings:
            self._store_model("MedSim.Finding", finding.finding_id, finding)
        self._store_model("MedSim.Scan", stored_scan.scan_id, stored_scan)
        self._project_fhir_resources(stored_scan)
        return stored_scan

    def _project_fhir_resources(self, scan: Scan) -> None:
        try:
            for finding in scan.findings:
                self._fhir_repository.put_resource(build_observation(finding))
            self._fhir_repository.put_resource(build_diagnostic_report(scan))
        except Exception:
            logger.exception("Failed to project scan %s into the IRIS FHIR repository", scan.scan_id)

    def list_findings(self, unit_id: str, domain: str | None = None, severity: str | None = None, room_id: str | None = None) -> list[Finding]:
        scans = [scan for scan in self.scans.values() if scan.unit_id == unit_id]
        findings = [finding for scan in scans for finding in scan.findings]
        if domain:
            findings = [finding for finding in findings if finding.domain == domain]
        if severity:
            findings = [finding for finding in findings if finding.severity == severity]
        if room_id:
            findings = [finding for finding in findings if finding.room_id == room_id]
        return findings

    def get_finding(self, finding_id: str) -> Finding:
        finding = self._load_json("MedSim.Finding", finding_id)
        if finding is not None:
            return Finding.model_validate(finding)
        for candidate in self._load_models("MedSim.Finding", Finding).values():
            if fhir_safe_id(candidate.finding_id) == finding_id:
                return candidate
        raise KeyError(finding_id)

    def list_models(self, unit_id: str) -> list[WorldModel]:
        return [model for model in self.models.values() if model.unit_id == unit_id]

    def get_model(self, unit_id: str) -> WorldModel:
        models = self.list_models(unit_id)
        if not models:
            raise KeyError(unit_id)
        return sorted(models, key=lambda item: item.created_at)[-1]

    def write_simulation(self, sim: ScenarioSimulation) -> ScenarioSimulation:
        return self._store_model("MedSim.ScenarioSimulation", sim.simulation_id, sim)

    def update_simulation(self, simulation_id: str, **updates: object) -> ScenarioSimulation:
        simulation = self._load_json("MedSim.ScenarioSimulation", simulation_id)
        if simulation is None:
            raise KeyError(simulation_id)
        for key, value in updates.items():
            simulation[key] = value
        updated = ScenarioSimulation.model_validate(simulation)
        return self._store_model("MedSim.ScenarioSimulation", simulation_id, updated)

    def get_simulation(self, simulation_id: str) -> ScenarioSimulation:
        simulation = self._load_json("MedSim.ScenarioSimulation", simulation_id)
        if simulation is None:
            raise KeyError(simulation_id)
        return ScenarioSimulation.model_validate(simulation)

    def list_simulations(self, unit_id: str) -> list[ScenarioSimulation]:
        simulations = [simulation for simulation in self.simulations.values() if simulation.unit_id == unit_id]
        return sorted(simulations, key=lambda item: item.triggered_at, reverse=True)

    def get_latest_simulation(self, unit_id: str) -> ScenarioSimulation:
        simulations = self.list_simulations(unit_id)
        if not simulations:
            raise KeyError(unit_id)
        return simulations[0]

    def get_diagnostic_report_resource(self, scan_id: str) -> dict[str, Any]:
        scan = self.scans.get(scan_id)
        if not scan:
            scan = next((item for item in self.scans.values() if fhir_safe_id(item.scan_id) == scan_id), None)
        if scan is None:
            raise KeyError(scan_id)
        resource = self._fhir_repository.get_resource("DiagnosticReport", fhir_safe_id(scan.scan_id))
        return resource or build_diagnostic_report(scan)

    def get_observation_resource(self, finding_id: str) -> dict[str, Any]:
        finding = self.get_finding(finding_id)
        resource = self._fhir_repository.get_resource("Observation", fhir_safe_id(finding.finding_id))
        return resource or build_observation(finding)

    def push_diagnostic_report(self, scan_id: str, target: str | None = None) -> dict[str, Any]:
        destination = (target or self._settings.iris_health_connect_endpoint).rstrip("/")
        if not destination:
            return {"status": "not_configured", "target": None, "scan_id": scan_id}

        report = self.get_diagnostic_report_resource(scan_id)
        observations: list[dict[str, Any]] = []
        for result in report.get("result", []):
            reference = result.get("reference", "")
            if not reference.startswith("Observation/"):
                continue
            observations.append(self.get_observation_resource(reference.split("/", 1)[1]))
        pushed = self._fhir_repository.push_bundle([*observations, report], target_base=destination)
        pushed["scan_id"] = scan_id
        return pushed


def create_iris_client() -> MemoryIRISClient | NativeIRISClient:
    settings = get_settings()
    if settings.iris_mode == "memory":
        return MemoryIRISClient()
    if settings.iris_mode == "fhir":
        return FHIRServiceIRISClient(settings)
    try:
        return NativeIRISClient(settings)
    except Exception:
        if settings.use_synthetic_fallbacks:
            logger.exception("Falling back to in-memory IRIS client after native connection failure")
            return MemoryIRISClient()
        raise


# Backwards-compatible constructor used by tests and older imports.
IRISClient = MemoryIRISClient
iris_client = create_iris_client()
