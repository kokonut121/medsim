from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from backend.db.iris_client import iris_client
from backend.models import PatientIntake, PatientIntakeCreate
from backend.reports.fhir_projector import build_condition_resource, build_patient_resource, fhir_safe_id


router = APIRouter(prefix="/api/fhir", tags=["fhir"])


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Existing scan / finding FHIR endpoints
# ---------------------------------------------------------------------------

@router.get("/DiagnosticReport/{scan_id}")
async def get_diagnostic_report(scan_id: str):
    try:
        return iris_client.get_diagnostic_report_resource(scan_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Scan not found")
    except Exception as exc:
        raise HTTPException(status_code=502, detail="FHIR repository request failed") from exc


@router.get("/Observation/{finding_id}")
async def get_observation(finding_id: str):
    try:
        return iris_client.get_observation_resource(finding_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Finding not found")
    except Exception as exc:
        raise HTTPException(status_code=502, detail="FHIR repository request failed") from exc


@router.post("/DiagnosticReport/$push")
async def push_diagnostic_report(payload: dict):
    scan_id = payload.get("scan_id")
    if not scan_id:
        raise HTTPException(status_code=400, detail="scan_id is required")
    try:
        return iris_client.push_diagnostic_report(scan_id, payload.get("target"))
    except KeyError:
        raise HTTPException(status_code=404, detail="Scan not found")
    except Exception as exc:
        raise HTTPException(status_code=502, detail="FHIR push failed") from exc


# ---------------------------------------------------------------------------
# Patient intake endpoints
# ---------------------------------------------------------------------------

@router.post("/Patient/$intake", status_code=201)
async def intake_patient(body: PatientIntakeCreate):
    """Register a pre-hospital patient intake.

    Generates a FHIR Patient + Condition resource, stores both in IRIS,
    embeds the chief complaint for vector similarity retrieval during
    crisis simulations and post-crisis diagnostics.
    """
    intake_id = f"intake_{uuid4().hex[:10]}"
    patient_fhir_id = fhir_safe_id(f"pat-{intake_id}")
    condition_fhir_id = fhir_safe_id(f"cond-{intake_id}")

    # Build the embedding asynchronously (OpenAI or keyword fallback)
    from backend.pipeline.patient_embedder import embed_intake
    embedding = await embed_intake(
        body.chief_complaint,
        body.mechanism,
        body.injury_severity,
    )

    intake = PatientIntake(
        intake_id=intake_id,
        unit_id=body.unit_id,
        chief_complaint=body.chief_complaint,
        injury_severity=body.injury_severity,
        mechanism=body.mechanism,
        vitals=body.vitals,
        eta_minutes=body.eta_minutes,
        age_estimate=body.age_estimate,
        sex=body.sex,
        received_at=_utcnow(),
        fhir_patient_id=patient_fhir_id,
        fhir_condition_id=condition_fhir_id,
        embedding=embedding,
    )

    iris_client.write_patient_intake(intake)

    # Build FHIR resources to return (already cached in iris_client)
    patient_res = build_patient_resource(intake)
    condition_res = build_condition_resource(intake)

    return {
        "intake_id": intake_id,
        "unit_id": body.unit_id,
        "fhir": {
            "Patient": patient_res,
            "Condition": condition_res,
        },
        "received_at": intake.received_at.isoformat(),
    }


@router.get("/Patient")
async def list_patient_intakes(unit_id: str = Query(..., description="Unit to list intakes for")):
    """List all active patient intakes for a unit, most recent first."""
    intakes = iris_client.list_patient_intakes(unit_id)
    return {
        "unit_id": unit_id,
        "count": len(intakes),
        "intakes": [
            {
                "intake_id": i.intake_id,
                "chief_complaint": i.chief_complaint,
                "injury_severity": i.injury_severity,
                "mechanism": i.mechanism,
                "eta_minutes": i.eta_minutes,
                "vitals": i.vitals.model_dump(exclude_none=True),
                "received_at": i.received_at.isoformat(),
                "fhir_patient_id": i.fhir_patient_id,
                "fhir_condition_id": i.fhir_condition_id,
            }
            for i in intakes
        ],
    }


@router.get("/Patient/{patient_id}")
async def get_patient(patient_id: str):
    """Retrieve a FHIR Patient resource by ID."""
    try:
        return iris_client.get_patient_fhir_resource(patient_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Patient not found")


@router.get("/Condition/{condition_id}")
async def get_condition(condition_id: str):
    """Retrieve a FHIR Condition resource by ID."""
    try:
        return iris_client.get_condition_fhir_resource(condition_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Condition not found")


@router.post("/Patient/$search")
async def search_patients(payload: dict):
    """Semantic similarity search over patient intakes.

    Body: { "unit_id": "...", "query": "stab wound chest", "top_k": 5 }

    Returns intakes whose chief-complaint embedding is most similar to
    the query — used by crisis simulation agents to retrieve relevant
    incoming patient context.
    """
    unit_id = payload.get("unit_id")
    query = payload.get("query", "")
    top_k = int(payload.get("top_k", 5))

    if not unit_id or not query:
        raise HTTPException(status_code=400, detail="unit_id and query are required")

    from backend.pipeline.patient_embedder import embed_intake
    query_embedding = await embed_intake(query, "", "immediate")

    results = iris_client.search_similar_intakes(query_embedding, unit_id, top_k=top_k)
    return {
        "unit_id": unit_id,
        "query": query,
        "results": [
            {
                "intake_id": i.intake_id,
                "chief_complaint": i.chief_complaint,
                "injury_severity": i.injury_severity,
                "mechanism": i.mechanism,
                "eta_minutes": i.eta_minutes,
                "received_at": i.received_at.isoformat(),
            }
            for i in results
        ],
    }
