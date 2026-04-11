from __future__ import annotations

import re
from datetime import datetime, timezone

from backend.models import Finding, Scan

# FHIR R4 requires code.coding on every Observation/DiagnosticReport.
# We use LOINC for the report and SNOMED CT for individual findings.
_REPORT_CODING = {
    "system": "http://loinc.org",
    "code": "11526-1",
    "display": "Pathology study",
}

# Domain → SNOMED CT finding codes (closest available codes for safety/workflow findings)
_DOMAIN_CODING: dict[str, dict[str, str]] = {
    "ICA": {"system": "http://snomed.info/sct", "code": "409073007", "display": "Infection control finding"},
    "MSA": {"system": "http://snomed.info/sct", "code": "182813001", "display": "Equipment maintenance finding"},
    "FRA": {"system": "http://snomed.info/sct", "code": "129839007", "display": "Fall risk finding"},
    "ERA": {"system": "http://snomed.info/sct", "code": "225368008", "display": "Emergency response finding"},
    "PFA": {"system": "http://snomed.info/sct", "code": "182992009", "display": "Patient flow finding"},
    "SCA": {"system": "http://snomed.info/sct", "code": "404684003", "display": "Clinical finding"},
}
_DEFAULT_CODING = {"system": "http://snomed.info/sct", "code": "404684003", "display": "Clinical finding"}

# Observation category: survey (closest to AI-generated assessment)
_OBS_CATEGORY = {
    "coding": [
        {
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "survey",
            "display": "Survey",
        }
    ]
}

# MedSim extension base URL
_EXT_BASE = "https://medsent.io/fhir/StructureDefinition"
_FHIR_ID_INVALID_CHARS = re.compile(r"[^A-Za-z0-9\-.]")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _scan_timestamp(scan: Scan) -> str:
    ts = getattr(scan, "created_at", None) or getattr(scan, "completed_at", None)
    if ts is None:
        return _now_iso()
    if hasattr(ts, "isoformat"):
        return ts.isoformat(timespec="seconds")
    return str(ts)


def _device_subject(unit_id: str) -> dict:
    """
    FHIR Observation/DiagnosticReport requires a subject.  Because MedSim
    scans a physical space (not a patient) we model the subject as a Device
    whose identifier is the unit being scanned.
    """
    return {"identifier": {"system": "https://medsent.io/units", "value": unit_id}}


def fhir_safe_id(value: str) -> str:
    sanitized = _FHIR_ID_INVALID_CHARS.sub("-", value).strip("-.")
    if not sanitized:
        sanitized = "medsent-resource"
    return sanitized[:64]


def build_diagnostic_report(scan: Scan) -> dict:
    timestamp = _scan_timestamp(scan)

    # One extension entry per domain status
    domain_extensions = []
    for domain, status in (getattr(scan, "domain_statuses", None) or {}).items():
        domain_extensions.append({
            "url": f"{_EXT_BASE}/domain-status",
            "extension": [
                {"url": "domain", "valueCode": domain},
                {"url": "status", "valueString": str(status)},
            ],
        })

    resource: dict = {
        "resourceType": "DiagnosticReport",
        "id": fhir_safe_id(scan.scan_id),
        "meta": {
            "profile": [f"{_EXT_BASE}/MedSimDiagnosticReport"],
        },
        "identifier": [
            {
                "system": "https://medsent.io/scans",
                "value": scan.scan_id,
            }
        ],
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                        "code": "OT",
                        "display": "Other",
                    }
                ]
            }
        ],
        "code": {
            "coding": [_REPORT_CODING],
            "text": f"MedSim Scan {scan.scan_id}",
        },
        "subject": _device_subject(scan.unit_id),
        "effectiveDateTime": timestamp,
        "issued": timestamp,
        "conclusion": f"{len(scan.findings)} findings synthesized for unit {scan.unit_id}",
        "result": [
            {"reference": f"Observation/{fhir_safe_id(finding.finding_id)}"}
            for finding in scan.findings
        ],
    }

    if domain_extensions:
        resource["extension"] = domain_extensions

    return resource


def build_observation(finding: Finding) -> dict:
    coding = _DOMAIN_CODING.get(getattr(finding, "domain", ""), _DEFAULT_CODING)

    resource: dict = {
        "resourceType": "Observation",
        "id": fhir_safe_id(finding.finding_id),
        "meta": {
            "profile": [f"{_EXT_BASE}/MedSimObservation"],
        },
        "identifier": [
            {
                "system": "https://medsent.io/findings",
                "value": finding.finding_id,
            }
        ],
        "status": "final",
        "category": [_OBS_CATEGORY],
        "code": {
            "coding": [coding],
            "text": f"{getattr(finding, 'domain', 'Unknown')} finding",
        },
        "subject": _device_subject(getattr(finding, "scan_id", "unknown")),
        "effectiveDateTime": _now_iso(),
        "valueString": finding.label_text,
        "note": [{"text": finding.recommendation}],
    }

    # Attach spatial anchor as a FHIR extension if present
    anchor = getattr(finding, "spatial_anchor", None)
    if anchor is not None:
        x = getattr(anchor, "x", None) if not isinstance(anchor, dict) else anchor.get("x")
        y = getattr(anchor, "y", None) if not isinstance(anchor, dict) else anchor.get("y")
        z = getattr(anchor, "z", None) if not isinstance(anchor, dict) else anchor.get("z")
        if x is not None and y is not None and z is not None:
            resource["extension"] = [
                {
                    "url": f"{_EXT_BASE}/spatial-anchor",
                    "extension": [
                        {"url": "x", "valueDecimal": float(x)},
                        {"url": "y", "valueDecimal": float(y)},
                        {"url": "z", "valueDecimal": float(z)},
                    ],
                }
            ]

    # Severity as an interpretation code
    severity = getattr(finding, "severity", None)
    if severity:
        sev_map = {
            "CRITICAL": ("H", "High"),
            "HIGH":     ("H", "High"),
            "ADVISORY": ("L", "Low"),
        }
        code, display = sev_map.get(str(severity).upper(), ("N", "Normal"))
        resource["interpretation"] = [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                        "code": code,
                        "display": display,
                    }
                ]
            }
        ]

    return resource
