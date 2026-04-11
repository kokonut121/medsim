from __future__ import annotations

import re
from datetime import datetime, timezone

from backend.models import Finding, PatientIntake, Scan

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


# ---------------------------------------------------------------------------
# Patient intake FHIR resources
# ---------------------------------------------------------------------------

# Mechanism keyword → ICD-10-CM code + display
_MECHANISM_ICD10: list[tuple[list[str], str, str]] = [
    (["stab", "puncture", "knife", "lacerat"],  "S21.9XXA", "Open wound, unspecified part of thorax, initial encounter"),
    (["gunshot", "bullet", "firearm"],           "S21.9XXA", "Penetrating wound, initial encounter"),
    (["burn", "fire", "scald", "thermal"],       "T30.0",    "Burn of unspecified body region, unspecified degree"),
    (["crush", "blunt", "mvc", "motor vehicle"], "S09.90XA", "Unspecified injury of head, initial encounter"),
    (["fall", "fell"],                            "W19.XXXA", "Unspecified fall, initial encounter"),
    (["overdose", "poison", "toxic"],            "T65.91XA", "Toxic effects of unspecified substance, initial encounter"),
    (["cardiac", "arrest", "chest pain"],        "I46.9",    "Cardiac arrest, cause unspecified"),
]
_DEFAULT_ICD10 = ("T14.90", "Injury, unspecified")


def _icd10_for(complaint: str, mechanism: str) -> tuple[str, str]:
    text = f"{complaint} {mechanism}".lower()
    for keywords, code, display in _MECHANISM_ICD10:
        if any(kw in text for kw in keywords):
            return code, display
    return _DEFAULT_ICD10


_SEV_SNOMED = {
    "immediate":  ("24484000",  "Severe (severity modifier)"),
    "delayed":    ("6736007",   "Moderate (severity modifier)"),
    "minor":      ("255604002", "Mild (severity modifier)"),
    "expectant":  ("442452003", "Life threatening severity"),
}


def build_patient_resource(intake: PatientIntake) -> dict:
    """Anonymous FHIR R4 Patient for a pre-hospital emergency intake."""
    resource: dict = {
        "resourceType": "Patient",
        "id": fhir_safe_id(intake.fhir_patient_id or intake.intake_id),
        "meta": {
            "profile": [f"{_EXT_BASE}/MedSimEmergencyPatient"],
        },
        "identifier": [
            {
                "system": "https://medsent.io/patient-intakes",
                "value": intake.intake_id,
            }
        ],
        "active": True,
        "name": [{"use": "anonymous", "text": f"Unknown-{intake.intake_id[-6:]}"}],
        "gender": intake.sex if intake.sex != "unknown" else "unknown",
    }
    if intake.age_estimate is not None:
        resource["extension"] = [
            {
                "url": f"{_EXT_BASE}/age-estimate",
                "valueInteger": intake.age_estimate,
            }
        ]
    return resource


def build_condition_resource(intake: PatientIntake) -> dict:
    """FHIR R4 Condition representing the patient's chief complaint + severity."""
    icd_code, icd_display = _icd10_for(intake.chief_complaint, intake.mechanism)
    sev_code, sev_display = _SEV_SNOMED.get(intake.injury_severity, ("24484000", "Severe"))
    patient_id = fhir_safe_id(intake.fhir_patient_id or intake.intake_id)
    condition_id = fhir_safe_id(intake.fhir_condition_id or f"cond-{intake.intake_id}")

    resource: dict = {
        "resourceType": "Condition",
        "id": condition_id,
        "meta": {
            "profile": [f"{_EXT_BASE}/MedSimEmergencyCondition"],
        },
        "identifier": [
            {
                "system": "https://medsent.io/conditions",
                "value": condition_id,
            }
        ],
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "active",
                }
            ]
        },
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                        "code": "encounter-diagnosis",
                        "display": "Encounter Diagnosis",
                    }
                ]
            }
        ],
        "severity": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": sev_code,
                    "display": sev_display,
                }
            ]
        },
        "code": {
            "coding": [
                {
                    "system": "http://hl7.org/fhir/sid/icd-10-cm",
                    "code": icd_code,
                    "display": icd_display,
                }
            ],
            "text": intake.chief_complaint,
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "recordedDate": intake.received_at.isoformat(timespec="seconds"),
        "note": [{"text": intake.mechanism}] if intake.mechanism else [],
    }

    # Attach vitals as FHIR extensions
    vitals = intake.vitals
    ext = []
    if vitals.heart_rate is not None:
        ext.append({"url": f"{_EXT_BASE}/vital-hr",  "valueInteger": vitals.heart_rate})
    if vitals.systolic_bp is not None:
        ext.append({"url": f"{_EXT_BASE}/vital-sbp", "valueInteger": vitals.systolic_bp})
    if vitals.spo2 is not None:
        ext.append({"url": f"{_EXT_BASE}/vital-spo2","valueInteger": vitals.spo2})
    if vitals.gcs is not None:
        ext.append({"url": f"{_EXT_BASE}/vital-gcs", "valueInteger": vitals.gcs})
    if vitals.eta_minutes := intake.eta_minutes:
        ext.append({"url": f"{_EXT_BASE}/eta-minutes","valueInteger": vitals.eta_minutes})
    if ext:
        resource["extension"] = ext

    return resource
