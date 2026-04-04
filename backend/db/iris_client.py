from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.models import CoverageMap, Facility, FacilityCreate, Finding, GapArea, Scan, Unit, WorldModel


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
        self.findings_by_scan: defaultdict[str, list[Finding]] = defaultdict(list)
        self.coverage_maps: dict[str, CoverageMap] = {}
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
                {"area_id": "main_entrance", "source": "street_view", "image_count": 8},
                {"area_id": "lobby", "source": "places_photos", "image_count": 11},
            ],
            gap_areas=[
                GapArea(area_id="icu_corridor_west", description="Interior corridor imagery missing"),
                GapArea(area_id="med_room_2", description="Medication preparation zone not visible"),
            ],
        )

    def list_facilities(self) -> list[Facility]:
        return list(self.facilities.values())

    def create_facility(self, payload: FacilityCreate) -> Facility:
        facility_id = f"fac_{uuid4().hex[:8]}"
        created = Facility(
            facility_id=facility_id,
            name=payload.name,
            address=payload.address,
            lat=41.881,
            lng=-87.623,
            org_id="org_demo",
            google_place_id=f"place_{facility_id}",
            osm_building_id=f"osm_{facility_id}",
            created_at=utcnow(),
        )
        self.facilities[facility_id] = created
        unit_id = f"{facility_id}_unit_1"
        self.units[unit_id] = Unit(
            unit_id=unit_id,
            facility_id=facility_id,
            name="Medical-Surgical Unit",
            floor=3,
            unit_type="MedSurg",
            created_at=utcnow(),
        )
        self.coverage_maps[facility_id] = CoverageMap(
            facility_id=facility_id,
            covered_areas=[],
            gap_areas=[GapArea(area_id="facility_pending", description="Imagery acquisition not started")],
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
        self.coverage_maps.pop(facility_id, None)

    def get_coverage(self, facility_id: str) -> CoverageMap:
        return self.coverage_maps[facility_id]

    def write_world_model(self, facility_id: str, world_model: dict) -> WorldModel:
        unit = next(unit for unit in self.units.values() if unit.facility_id == facility_id)
        model = WorldModel(
            model_id=f"model_{uuid4().hex[:8]}",
            unit_id=unit.unit_id,
            status="ready",
            splat_r2_key=world_model["splat_url"],
            scene_graph_json=world_model["scene_manifest"],
            world_labs_world_id=world_model["world_id"],
            created_at=utcnow(),
            completed_at=utcnow(),
        )
        self.models[model.model_id] = model
        return model

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

