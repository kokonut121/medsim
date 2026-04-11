"""
Agentic Scan Orchestrator
=========================
Background-task-driven scan lifecycle that matches the scenario simulation pattern.

  POST /api/scans/{unit_id}/run  →  returns Scan(status=queued) immediately
  BackgroundTask: run_scan_background  →  streams typed events via Redis

Event types published to scan:{unit_id}:
  status        — scan-level phase transitions (queued→running→synthesizing→complete/failed)
  domain_status — per-domain progress and finding count
  finding       — grounded finding candidate (survives domain validation)
  complete      — final persisted Scan
  failed        — terminal error payload
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from backend.agents.consensus import agentic_consensus, consensus_synthesis_engine
from backend.agents.grounding import ground_candidates
from backend.agents.swarm import run_domain_swarm
from backend.db.iris_client import iris_client
from backend.db.redis_client import redis_client
from backend.models import DomainStatus, Finding, Scan
from backend.pipeline.spatial_bundle import build_spatial_bundle

logger = logging.getLogger(__name__)

DOMAINS = ("ICA", "MSA", "FRA", "ERA", "PFA", "SCA")


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _get_provider():
    from backend.config import get_settings
    settings = get_settings()
    if settings.use_synthetic_fallbacks or not settings.openai_api_key:
        from backend.agents.providers.synthetic import SyntheticProvider
        return SyntheticProvider()
    from backend.agents.providers.openai_provider import OpenAIProvider
    return OpenAIProvider(model="gpt-4o-mini")


async def _pub(unit_id: str, payload: dict) -> None:
    try:
        await redis_client.publish(f"scan:{unit_id}", payload)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Domain worker
# ---------------------------------------------------------------------------

async def _run_domain(
    unit_id: str,
    scan_id: str,
    domain: str,
    bundle: dict,
    provider,
    started_at: datetime,
) -> tuple[str, list[dict]]:
    await _pub(unit_id, {
        "type": "domain_status",
        "scan_id": scan_id,
        "domain": domain,
        "status": "running",
    })

    try:
        raw = await run_domain_swarm(provider, domain, bundle)
    except Exception as exc:
        logger.warning("Domain %s swarm failed: %s", domain, exc)
        raw = []

    grounded = ground_candidates(raw, bundle, scan_id)

    await _pub(unit_id, {
        "type": "domain_status",
        "scan_id": scan_id,
        "domain": domain,
        "status": "complete",
        "finding_count": len(grounded),
    })

    for f in grounded:
        await _pub(unit_id, {"type": "finding", "scan_id": scan_id, **f})

    return domain, grounded


# ---------------------------------------------------------------------------
# Background scan lifecycle
# ---------------------------------------------------------------------------

async def run_scan_background(unit_id: str, scan_id: str) -> None:
    """Full agentic scan. Called as a BackgroundTask."""
    # Retrieve model
    try:
        model = iris_client.get_model(unit_id)
    except KeyError:
        await _pub(unit_id, {"type": "failed", "scan_id": scan_id, "error": f"No model for {unit_id}"})
        iris_client.update_scan_status(scan_id, "failed")
        return

    # Build (or reuse) spatial bundle
    bundle = model.spatial_bundle_json
    if not bundle:
        bundle = build_spatial_bundle(model.scene_graph_json)
        iris_client.update_model(model.model_id, spatial_bundle_json=bundle)

    await _pub(unit_id, {"type": "status", "scan_id": scan_id, "status": "running"})
    iris_client.update_scan_status(scan_id, "running")

    provider = _get_provider()
    started_at = _utcnow()

    # All domain swarms in parallel
    tasks = [
        _run_domain(unit_id, scan_id, domain, bundle, provider, started_at)
        for domain in DOMAINS
    ]
    domain_results = await asyncio.gather(*tasks, return_exceptions=True)

    all_grounded: list[dict] = []
    domain_statuses: dict[str, DomainStatus] = {}
    completed_at = _utcnow()

    for result in domain_results:
        if isinstance(result, Exception):
            logger.warning("Domain task failed: %s", result)
            continue
        domain, findings = result
        all_grounded.extend(findings)
        domain_statuses[domain] = DomainStatus(
            status="complete",
            finding_count=len(findings),
            started_at=started_at,
            completed_at=completed_at,
        )

    for domain in DOMAINS:
        if domain not in domain_statuses:
            domain_statuses[domain] = DomainStatus(
                status="complete",
                finding_count=0,
                started_at=started_at,
                completed_at=completed_at,
            )

    # Synthesizing pass
    await _pub(unit_id, {"type": "status", "scan_id": scan_id, "status": "synthesizing"})
    iris_client.update_scan_status(scan_id, "synthesizing")

    try:
        final_dicts = await agentic_consensus(all_grounded, bundle, provider)
    except Exception as exc:
        logger.warning("Agentic consensus failed, falling back: %s", exc)
        final_dicts = consensus_synthesis_engine([[f] for f in all_grounded])

    # If LLM providers returned nothing at all (synthetic fallback), fall back to rule-based teams
    if not final_dicts:
        final_dicts = _rule_based_fallback(scan_id, model, bundle)

    try:
        findings = [Finding.model_validate(f) for f in final_dicts]
    except Exception as exc:
        logger.warning("Finding validation failed: %s", exc)
        findings = []

    scan = iris_client.get_scan(scan_id)
    final_scan = Scan(
        scan_id=scan_id,
        unit_id=unit_id,
        status="complete",
        domain_statuses=domain_statuses,
        findings=findings,
        triggered_at=scan.triggered_at,
        completed_at=_utcnow(),
    )
    iris_client.write_findings(final_scan, findings)

    await _pub(unit_id, {
        "type": "complete",
        "scan_id": scan_id,
        "scan": final_scan.model_dump(mode="json"),
    })


# ---------------------------------------------------------------------------
# Rule-based fallback (when no LLM key / synthetic mode)
# ---------------------------------------------------------------------------

def _rule_based_fallback(scan_id: str, model, bundle: dict) -> list[dict]:
    """Run the original deterministic rule-based teams as fallback."""
    import asyncio as _asyncio
    from backend.agents import era_team, fra_team, ica_team, msa_team, pfa_team, sca_team
    from backend.agents.consensus import consensus_synthesis_engine

    world_dict = model.model_dump()
    try:
        loop = _asyncio.get_event_loop()
        raw_results = loop.run_until_complete(asyncio.gather(
            ica_team.run(scan_id, world_dict),
            msa_team.run(scan_id, world_dict),
            fra_team.run(scan_id, world_dict),
            era_team.run(scan_id, world_dict),
            pfa_team.run(scan_id, world_dict),
            sca_team.run(scan_id, world_dict),
        ))
    except RuntimeError:
        # Already in async context — use asyncio.create_task
        import concurrent.futures
        import threading

        result_holder: list = []

        def _run_sync():
            new_loop = _asyncio.new_event_loop()
            _asyncio.set_event_loop(new_loop)
            try:
                result_holder.append(new_loop.run_until_complete(asyncio.gather(
                    ica_team.run(scan_id, world_dict),
                    msa_team.run(scan_id, world_dict),
                    fra_team.run(scan_id, world_dict),
                    era_team.run(scan_id, world_dict),
                    pfa_team.run(scan_id, world_dict),
                    sca_team.run(scan_id, world_dict),
                )))
            finally:
                new_loop.close()
                _asyncio.set_event_loop(None)

        t = threading.Thread(target=_run_sync)
        t.start()
        t.join()
        raw_results = result_holder[0] if result_holder else [[], [], [], [], [], []]

    return consensus_synthesis_engine(raw_results)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_scan(unit_id: str) -> Scan:
    """Create and persist a queued Scan. Returns immediately."""
    scan_id = f"scan_{uuid4().hex[:8]}"
    scan = Scan(
        scan_id=scan_id,
        unit_id=unit_id,
        status="queued",
        domain_statuses={
            d: DomainStatus(status="queued", finding_count=0)
            for d in DOMAINS
        },
        findings=[],
        triggered_at=_utcnow(),
    )
    iris_client.write_scan(scan)
    return scan


async def run_scan(unit_id: str, world_model_id: str) -> Scan:
    """Backward-compatible synchronous entry point (startup auto-scan)."""
    scan = create_scan(unit_id)
    await run_scan_background(unit_id, scan.scan_id)
    return iris_client.get_scan(scan.scan_id)
