from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from backend.config import Settings, get_settings
from backend.db.fhir_repository import FHIRRepositoryClient
from backend.models import CoverageArea, CoverageMap, Facility, FacilityCreate, Finding, GapArea, ImageMeta, Scan, Unit, WorldModel
from backend.reports.fhir_projector import build_diagnostic_report, build_observation


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
        self._seed_demo_data()

    def _seed_demo_data(self) -> None:
        if self.facilities:
            return

        facility_id = "fac_demo"
        created_at = utcnow() - timedelta(days=2)
        facility = Facility(
            facility_id=facility_id,
            name="Northwestern Memorial — Trauma Center",
            address="251 E Huron St, Chicago, IL 60611",
            lat=41.8949406,
            lng=-87.621438,
            org_id="org_demo",
            google_place_id="ChIJa7pTLKssDogRN-wo98jjo6A",
            osm_building_id="osm-demo-1",
            created_at=created_at,
        )
        self.facilities[facility_id] = facility

        for index, unit_type in enumerate(["ED", "ICU"], start=1):
            unit_id = f"unit_{index}"
            self.units[unit_id] = Unit(
                unit_id=unit_id,
                facility_id=facility_id,
                name=f"{unit_type} Unit",
                floor=index,
                unit_type=unit_type,
                created_at=created_at,
            )

        scene_graph = {
            "units": [
                {
                    "unit_id": "unit_1",
                    "unit_type": "Trauma Center",
                    "rooms": [
                        # ── Ambulance Bay ──────────────────────────────────────
                        {
                            "room_id": "TC-ENTRY",
                            "type": "ed_entrance_ambulance_bay",
                            "area_sqft_estimate": 700,
                            "equipment": [
                                {"type": "hand_hygiene_dispenser", "position": "bay door right", "accessible": True, "confidence": 0.95},
                            ],
                            "adjacency": ["TC-CORRIDOR"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "street_view",
                            "grid_col": 0, "grid_row": 0,
                        },
                        # ── Main Trauma Corridor ───────────────────────────────
                        {
                            "room_id": "TC-CORRIDOR",
                            "type": "corridor_hallway",
                            "area_sqft_estimate": 1200,
                            "equipment": [
                                {"type": "crash_cart", "position": "far end alcove — 90ft from TB-3", "accessible": True, "confidence": 0.90},
                            ],
                            "adjacency": ["TC-ENTRY", "TB-1", "TB-2", "TB-3", "TC-RESUS", "TC-NS", "TC-MED", "TC-OR", "TC-CT", "TC-SUPPLY"],
                            "sightline_to_nursing_station": True,
                            "image_source_quality": "places",
                            "grid_col": 0, "grid_row": 1,
                        },
                        # ── Trauma Bays (north side of corridor) ──────────────
                        {
                            "room_id": "TB-1",
                            "type": "icu_bay",
                            "area_sqft_estimate": 380,
                            "equipment": [
                                {"type": "monitor", "position": "ceiling boom", "accessible": True, "confidence": 0.96},
                                {"type": "ventilator", "position": "head of bay", "accessible": True, "confidence": 0.93},
                                {"type": "iv_pole", "position": "left rail", "accessible": True, "confidence": 0.91},
                                {"type": "hand_hygiene_dispenser", "position": "bay entry left", "accessible": True, "confidence": 0.94},
                            ],
                            "adjacency": ["TC-CORRIDOR"],
                            "sightline_to_nursing_station": True,
                            "image_source_quality": "places",
                            "grid_col": 0, "grid_row": 2,
                        },
                        {
                            "room_id": "TB-2",
                            "type": "icu_bay",
                            "area_sqft_estimate": 380,
                            "equipment": [
                                {"type": "monitor", "position": "ceiling boom", "accessible": True, "confidence": 0.95},
                                {"type": "ventilator", "position": "head of bay", "accessible": True, "confidence": 0.92},
                                {"type": "iv_pole", "position": "right rail", "accessible": True, "confidence": 0.90},
                                {"type": "hand_hygiene_dispenser", "position": "bay entry — inaccessible behind cart", "accessible": False, "confidence": 0.71},
                            ],
                            "adjacency": ["TC-CORRIDOR"],
                            "sightline_to_nursing_station": True,
                            "image_source_quality": "places",
                            "grid_col": 1, "grid_row": 2,
                        },
                        {
                            "room_id": "TB-3",
                            "type": "icu_bay",
                            "area_sqft_estimate": 380,
                            "equipment": [
                                {"type": "monitor", "position": "ceiling boom", "accessible": True, "confidence": 0.94},
                                {"type": "ventilator", "position": "head of bay", "accessible": True, "confidence": 0.91},
                                {"type": "call_light", "position": "missing", "accessible": False, "confidence": 0.62},
                            ],
                            "adjacency": ["TC-CORRIDOR"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "places",
                            "grid_col": 2, "grid_row": 2,
                        },
                        # ── Resuscitation Room ─────────────────────────────────
                        {
                            "room_id": "TC-RESUS",
                            "type": "operating_room",
                            "area_sqft_estimate": 500,
                            "equipment": [
                                {"type": "monitor", "position": "dual ceiling arms", "accessible": True, "confidence": 0.97},
                                {"type": "ventilator", "position": "anesthesia station", "accessible": True, "confidence": 0.96},
                                {"type": "hand_hygiene_dispenser", "position": "scrub sink outside", "accessible": True, "confidence": 0.95},
                                {"type": "crash_cart", "position": "MISSING — not stocked here", "accessible": False, "confidence": 0.60},
                            ],
                            "adjacency": ["TC-CORRIDOR", "TC-OR"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "places",
                            "grid_col": 3, "grid_row": 2,
                        },
                        # ── Nursing Station ────────────────────────────────────
                        {
                            "room_id": "TC-NS",
                            "type": "nursing_station",
                            "area_sqft_estimate": 320,
                            "equipment": [
                                {"type": "workstation", "position": "central desk — 3 terminals", "accessible": True, "confidence": 0.97},
                                {"type": "hand_hygiene_dispenser", "position": "desk entry both sides", "accessible": True, "confidence": 0.96},
                            ],
                            "adjacency": ["TC-CORRIDOR"],
                            "sightline_to_nursing_station": True,
                            "image_source_quality": "places",
                            "grid_col": 0, "grid_row": 3,
                        },
                        # ── Medication Room ────────────────────────────────────
                        {
                            "room_id": "TC-MED",
                            "type": "medication_room_pharmacy",
                            "area_sqft_estimate": 180,
                            "equipment": [
                                {"type": "adc", "position": "back wall — single unit", "accessible": True, "confidence": 0.95},
                                {"type": "workstation", "position": "counter", "accessible": True, "confidence": 0.91},
                            ],
                            "adjacency": ["TC-CORRIDOR"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "places",
                            "grid_col": 1, "grid_row": 3,
                        },
                        # ── Trauma OR ──────────────────────────────────────────
                        {
                            "room_id": "TC-OR",
                            "type": "operating_room",
                            "area_sqft_estimate": 600,
                            "equipment": [
                                {"type": "monitor", "position": "OR boom", "accessible": True, "confidence": 0.97},
                                {"type": "ventilator", "position": "anesthesia station", "accessible": True, "confidence": 0.96},
                                {"type": "hand_hygiene_dispenser", "position": "scrub sink", "accessible": True, "confidence": 0.98},
                            ],
                            "adjacency": ["TC-CORRIDOR", "TC-RESUS"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "places",
                            "grid_col": 2, "grid_row": 3,
                        },
                        # ── CT / Radiology ─────────────────────────────────────
                        {
                            "room_id": "TC-CT",
                            "type": "utility_support",
                            "area_sqft_estimate": 420,
                            "equipment": [
                                {"type": "monitor", "position": "control console", "accessible": True, "confidence": 0.94},
                            ],
                            "adjacency": ["TC-CORRIDOR"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "street_view",
                            "grid_col": 3, "grid_row": 3,
                        },
                        # ── Supply / Clean Utility ─────────────────────────────
                        {
                            "room_id": "TC-SUPPLY",
                            "type": "utility_support",
                            "area_sqft_estimate": 160,
                            "equipment": [
                                {"type": "hand_hygiene_dispenser", "position": "door entry", "accessible": True, "confidence": 0.89},
                            ],
                            "adjacency": ["TC-CORRIDOR"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "street_view",
                            "grid_col": 4, "grid_row": 3,
                        },
                    ],
                }
            ],
            "flow_annotations": {
                "patient_flow_paths": [["TC-ENTRY", "TC-CORRIDOR", "TB-1"]],
                "staff_flow_paths": [["TC-NS", "TC-CORRIDOR", "TC-MED", "TB-2"]],
                "clean_corridors": ["TC-CORRIDOR"],
                "dirty_corridors": ["TC-SUPPLY"],
            },
        }
        self.models["model_unit_1"] = WorldModel(
            model_id="model_unit_1",
            unit_id="unit_1",
            status="ready",
            splat_r2_key="facilities/fac_demo/models/65bab75f-b181-4314-be3a-3b3cb88c3deb/scene.spz",
            scene_graph_json=scene_graph,
            world_labs_world_id="65bab75f-b181-4314-be3a-3b3cb88c3deb",
            world_marble_url="https://marble.worldlabs.ai/world/65bab75f-b181-4314-be3a-3b3cb88c3deb",
            caption="Northwestern Memorial — Trauma Center world model (VR video extraction)",
            source_image_count=13,
            created_at=created_at,
            completed_at=created_at + timedelta(hours=1),
        )

        self.coverage_maps[facility_id] = CoverageMap(
            facility_id=facility_id,
            covered_areas=[
                CoverageArea(area_id="main_entrance", source="street_view", image_count=8, category="building_exterior"),
                CoverageArea(area_id="lobby", source="places_photos", image_count=11, category="lobby_main_entrance"),
            ],
            gap_areas=[
                GapArea(area_id="icu_corridor_west", description="Interior corridor imagery missing"),
                GapArea(area_id="med_room_2", description="Medication preparation zone not visible"),
            ],
            updated_at=created_at,
        )

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
        models = [model for model in self.models.values() if model.unit_id in {unit.unit_id for unit in units}]
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

    def write_findings(self, scan: Scan, findings: list[Finding]) -> Scan:
        scan.findings = findings
        self.findings_by_scan[scan.scan_id] = findings
        self.scans[scan.scan_id] = scan
        return scan

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
        for findings in self.findings_by_scan.values():
            for finding in findings:
                if finding.finding_id == finding_id:
                    return finding
        raise KeyError(finding_id)

    def list_models(self, unit_id: str) -> list[WorldModel]:
        return [model for model in self.models.values() if model.unit_id == unit_id]

    def get_model(self, unit_id: str) -> WorldModel:
        models = self.list_models(unit_id)
        if not models:
            raise KeyError(unit_id)
        return sorted(models, key=lambda item: item.created_at)[-1]

    def get_diagnostic_report_resource(self, scan_id: str) -> dict[str, Any]:
        scan = self.scans.get(scan_id)
        if not scan:
            raise KeyError(scan_id)
        return build_diagnostic_report(scan)

    def get_observation_resource(self, finding_id: str) -> dict[str, Any]:
        return build_observation(self.get_finding(finding_id))

    def push_diagnostic_report(self, scan_id: str, target: str | None = None) -> dict[str, Any]:
        return {"status": "not_configured", "target": target, "scan_id": scan_id}


class NativeIRISClient:
    mode = "native"

    def __init__(self, settings: Settings) -> None:
        try:
            import iris
        except ImportError as exc:
            raise RuntimeError(
                "InterSystems native mode requires the 'intersystems-irispython' package. "
                "Install backend dependencies before setting MEDSENTINEL_IRIS_MODE=native."
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
        self._fhir_repository = FHIRRepositoryClient(
            base_url=settings.iris_fhir_base,
            username=settings.iris_user,
            password=settings.iris_password,
        )
        self.upload_sessions: dict[str, dict[str, Any]] = {}
        self._seed_demo_data()

    @property
    def facilities(self) -> dict[str, Facility]:
        return self._load_models("MedSentinel.Facility", Facility)

    @property
    def units(self) -> dict[str, Unit]:
        return self._load_models("MedSentinel.Unit", Unit)

    @property
    def models(self) -> dict[str, WorldModel]:
        return self._load_models("MedSentinel.WorldModel", WorldModel)

    @property
    def scans(self) -> dict[str, Scan]:
        return self._load_models("MedSentinel.Scan", Scan)

    @property
    def images(self) -> dict[str, ImageMeta]:
        return self._load_models("MedSentinel.ImageMeta", ImageMeta)

    @property
    def coverage_maps(self) -> dict[str, CoverageMap]:
        return self._load_models("MedSentinel.CoverageMap", CoverageMap)

    @property
    def findings_by_scan(self) -> defaultdict[str, list[Finding]]:
        grouped: defaultdict[str, list[Finding]] = defaultdict(list)
        for finding in self._load_models("MedSentinel.Finding", Finding).values():
            grouped[finding.scan_id].append(finding)
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
            self._store_model("MedSentinel.Facility", facility.facility_id, facility)
        for unit in memory.units.values():
            self._store_model("MedSentinel.Unit", unit.unit_id, unit)
        for model in memory.models.values():
            self._store_model("MedSentinel.WorldModel", model.model_id, model)
        for coverage in memory.coverage_maps.values():
            self._store_model("MedSentinel.CoverageMap", coverage.facility_id, coverage)

    def _store_json(self, global_name: str, record_id: str, payload: dict[str, Any]) -> None:
        self._iris.node(global_name)[record_id] = json.dumps(payload)

    def _load_json(self, global_name: str, record_id: str) -> dict[str, Any] | None:
        raw = self._iris.node(global_name).get(record_id)
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
        self._store_model("MedSentinel.Facility", facility_id, created)

        unit = Unit(
            unit_id=f"{facility_id}_unit_1",
            facility_id=facility_id,
            name=payload.unit_name or "Trauma Center",
            floor=payload.floor,
            unit_type=payload.unit_type or "Trauma",
            created_at=utcnow(),
        )
        self._store_model("MedSentinel.Unit", unit.unit_id, unit)

        coverage = CoverageMap(
            facility_id=facility_id,
            covered_areas=[],
            gap_areas=[GapArea(area_id="facility_pending", description="Imagery acquisition not started")],
            updated_at=utcnow(),
        )
        self._store_model("MedSentinel.CoverageMap", facility_id, coverage)
        return created

    def get_facility(self, facility_id: str) -> dict[str, Any]:
        facility = self.facilities[facility_id]
        units = [unit for unit in self.units.values() if unit.facility_id == facility_id]
        models = [model for model in self.models.values() if model.unit_id in {unit.unit_id for unit in units}]
        return {"facility": facility, "units": units, "models": models}

    def delete_facility(self, facility_id: str) -> None:
        doomed_units = [unit_id for unit_id, unit in self.units.items() if unit.facility_id == facility_id]
        doomed_models = [model_id for model_id, model in self.models.items() if model.unit_id in doomed_units]
        doomed_images = [image_id for image_id, image in self.images.items() if image.facility_id == facility_id]
        for unit_id in doomed_units:
            self._delete_record("MedSentinel.Unit", unit_id)
        for model_id in doomed_models:
            self._delete_record("MedSentinel.WorldModel", model_id)
        for image_id in doomed_images:
            self._delete_record("MedSentinel.ImageMeta", image_id)
        for scan_id, scan in self.scans.items():
            if scan.unit_id in doomed_units:
                for finding in scan.findings:
                    self._delete_record("MedSentinel.Finding", finding.finding_id)
                self._delete_record("MedSentinel.Scan", scan_id)
        self._delete_record("MedSentinel.CoverageMap", facility_id)
        self._delete_record("MedSentinel.Facility", facility_id)

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
        return self._store_model("MedSentinel.WorldModel", model.model_id, model)

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
        updated = WorldModel.model_validate(updates)
        return self._store_model("MedSentinel.WorldModel", model_id, updated)

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
        return self._store_model("MedSentinel.WorldModel", ready_model.model_id, ready_model)

    def write_image_meta(self, image_meta: ImageMeta) -> ImageMeta:
        return self._store_model("MedSentinel.ImageMeta", image_meta.image_id, image_meta)

    def update_image_classification(self, image_id: str, *, category: str, confidence: float, notes: str | None = None) -> ImageMeta:
        image = self.images[image_id]
        updates = image.model_dump()
        updates["category"] = category
        updates["confidence"] = confidence
        updates["notes"] = notes
        updated = ImageMeta.model_validate(updates)
        return self._store_model("MedSentinel.ImageMeta", image_id, updated)

    def list_images_for_facility(self, facility_id: str) -> list[ImageMeta]:
        return [image for image in self.images.values() if image.facility_id == facility_id]

    def update_coverage(self, facility_id: str, covered_areas: list[CoverageArea], gap_areas: list[GapArea]) -> CoverageMap:
        coverage = CoverageMap(
            facility_id=facility_id,
            covered_areas=covered_areas,
            gap_areas=gap_areas,
            updated_at=utcnow(),
        )
        return self._store_model("MedSentinel.CoverageMap", facility_id, coverage)

    def create_upload_session(self, upload_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.upload_sessions[upload_id] = payload
        return self.upload_sessions[upload_id]

    def get_upload_session(self, upload_id: str) -> dict[str, Any]:
        return self.upload_sessions[upload_id]

    def update_upload_session(self, upload_id: str, **updates: object) -> dict[str, Any]:
        session = self.upload_sessions[upload_id]
        session.update(updates)
        return session

    def write_findings(self, scan: Scan, findings: list[Finding]) -> Scan:
        stored_scan = scan.model_copy(update={"findings": findings})
        for finding in findings:
            self._store_model("MedSentinel.Finding", finding.finding_id, finding)
        self._store_model("MedSentinel.Scan", stored_scan.scan_id, stored_scan)
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
        finding = self._load_json("MedSentinel.Finding", finding_id)
        if finding is None:
            raise KeyError(finding_id)
        return Finding.model_validate(finding)

    def list_models(self, unit_id: str) -> list[WorldModel]:
        return [model for model in self.models.values() if model.unit_id == unit_id]

    def get_model(self, unit_id: str) -> WorldModel:
        models = self.list_models(unit_id)
        if not models:
            raise KeyError(unit_id)
        return sorted(models, key=lambda item: item.created_at)[-1]

    def get_diagnostic_report_resource(self, scan_id: str) -> dict[str, Any]:
        scan = self.scans.get(scan_id)
        if not scan:
            raise KeyError(scan_id)
        resource = self._fhir_repository.get_resource("DiagnosticReport", scan_id)
        return resource or build_diagnostic_report(scan)

    def get_observation_resource(self, finding_id: str) -> dict[str, Any]:
        finding = self.get_finding(finding_id)
        resource = self._fhir_repository.get_resource("Observation", finding_id)
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
    if settings.iris_mode != "native":
        return MemoryIRISClient()
    try:
        return NativeIRISClient(settings)
    except Exception:
        if settings.use_synthetic_fallbacks:
            logger.exception("Falling back to in-memory IRIS client after native connection failure")
            return MemoryIRISClient()
        raise


iris_client = create_iris_client()
