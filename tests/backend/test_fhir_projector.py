from datetime import datetime, timezone

from backend.models import DomainStatus, PatientIntake, PatientVitals, Scan
from backend.reports.fhir_projector import build_condition_resource, build_diagnostic_report


def test_build_condition_resource_includes_eta_extension():
    intake = PatientIntake(
        intake_id="intake_demo",
        unit_id="unit_1",
        chief_complaint="stab wound to left chest",
        injury_severity="immediate",
        mechanism="penetrating trauma",
        vitals=PatientVitals(heart_rate=132, systolic_bp=84, spo2=91, gcs=12),
        eta_minutes=7,
        received_at=datetime(2026, 4, 11, 8, 0, tzinfo=timezone.utc),
    )

    resource = build_condition_resource(intake)

    assert resource["resourceType"] == "Condition"
    extensions = {item["url"]: item["valueInteger"] for item in resource.get("extension", [])}
    assert extensions["https://medsent.io/fhir/StructureDefinition/eta-minutes"] == 7
    assert extensions["https://medsent.io/fhir/StructureDefinition/vital-hr"] == 132


def test_build_diagnostic_report_omits_empty_result():
    scan = Scan(
        scan_id="scan_empty",
        unit_id="unit_1",
        status="complete",
        domain_statuses={
            domain: DomainStatus(status="complete", finding_count=0)
            for domain in ("ICA", "MSA", "FRA", "ERA", "PFA", "SCA")
        },
        findings=[],
        triggered_at=datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 4, 12, 9, 1, tzinfo=timezone.utc),
    )

    resource = build_diagnostic_report(scan)

    assert resource["resourceType"] == "DiagnosticReport"
    assert "result" not in resource
