from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.models import CoverageArea, CoverageMap, Facility, FacilityCreate, Finding, GapArea, ImageMeta, Scan, Unit, WorldModel


UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


class IRISClient:
    """
    In-memory development stand-in for InterSystems IRIS.
    The public interface mirrors the PRD so the app can be swapped to the
    real SDK later without changing route logic.
    """

    def __init__(self) -> None:
        self.facilities: dict[str, Facility] = {}
        self.units: dict[str, Unit] = {}
        self.models: dict[str, WorldModel] = {}
        self.scans: dict[str, Scan] = {}
        self.images: dict[str, ImageMeta] = {}
        self.images_by_facility: defaultdict[str, list[str]] = defaultdict(list)
        self.findings_by_scan: defaultdict[str, list[Finding]] = defaultdict(list)
        self.coverage_maps: dict[str, CoverageMap] = {}
        self.upload_sessions: dict[str, dict] = {}
        self._seed_demo_data()

    def _seed_demo_data(self) -> None:
        if self.facilities:
            return

        facility_id = "fac_demo"
        created_at = utcnow() - timedelta(days=2)
        facility = Facility(
            facility_id=facility_id,
            name="MedSentinel Academic Medical Center",
            address="123 Health Ave, Chicago, IL",
            lat=41.8781,
            lng=-87.6298,
            org_id="org_demo",
            google_place_id="demo-place",
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
                    "unit_type": "ED",
                    "rooms": [
                        {
                            "room_id": "ED-101",
                            "type": "patient_room",
                            "area_sqft_estimate": 180,
                            "equipment": [
                                {
                                    "type": "crash_cart",
                                    "position": "north corridor alcove",
                                    "accessible": True,
                                    "confidence": 0.92,
                                }
                            ],
                            "adjacency": ["ED-CORE"],
                            "sightline_to_nursing_station": False,
                            "image_source_quality": "places",
                        }
                    ],
                }
            ],
            "flow_annotations": {
                "patient_flow_paths": [["ED-ENTRY", "ED-CORE", "ED-101"]],
                "staff_flow_paths": [["ED-DESK", "ED-CORE", "ED-101"]],
                "clean_corridors": ["ED-C1"],
                "dirty_corridors": ["ED-C2"],
            },
        }
        self.models["model_unit_1"] = WorldModel(
            model_id="model_unit_1",
            unit_id="unit_1",
            status="ready",
            splat_r2_key="worlds/unit_1/demo.splat",
            scene_graph_json=scene_graph,
            world_labs_world_id="world_demo_1",
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

    def get_facility(self, facility_id: str) -> dict:
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

    def write_world_model(self, facility_id: str, world_model: dict, model_id: str | None = None) -> WorldModel:
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

    def create_upload_session(self, upload_id: str, payload: dict) -> dict:
        self.upload_sessions[upload_id] = payload
        return self.upload_sessions[upload_id]

    def get_upload_session(self, upload_id: str) -> dict:
        return self.upload_sessions[upload_id]

    def update_upload_session(self, upload_id: str, **updates: object) -> dict:
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


iris_client = IRISClient()
