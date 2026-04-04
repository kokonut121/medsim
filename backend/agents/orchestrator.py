from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from backend.agents.consensus import consensus_synthesis_engine
from backend.agents import era_team, fra_team, ica_team, msa_team, pfa_team, sca_team
from backend.db.iris_client import iris_client
from backend.db.redis_client import redis_client
from backend.models import DomainStatus, Finding, Scan


DOMAINS = ("ICA", "MSA", "FRA", "ERA", "PFA", "SCA")


async def _publish_findings(unit_id: str, findings: list[Finding]) -> None:
    for finding in findings:
        await redis_client.publish(f"scan:{unit_id}", finding.model_dump(mode="json"))


async def run_scan(unit_id: str, world_model_id: str) -> Scan:
    world_model = iris_client.get_model(unit_id)
    scan_id = f"scan_{uuid4().hex[:8]}"
    started_at = datetime.now(tz=timezone.utc)
    raw_results = await asyncio.gather(
        ica_team.run(scan_id, world_model.model_dump()),
        msa_team.run(scan_id, world_model.model_dump()),
        fra_team.run(scan_id, world_model.model_dump()),
        era_team.run(scan_id, world_model.model_dump()),
        pfa_team.run(scan_id, world_model.model_dump()),
        sca_team.run(scan_id, world_model.model_dump()),
    )
    merged = consensus_synthesis_engine(raw_results)
    findings = [Finding.model_validate(finding) for finding in merged]
    completed_at = datetime.now(tz=timezone.utc)
    domain_statuses = {
        domain: DomainStatus(
            status="complete",
            finding_count=len([finding for finding in findings if finding.domain == domain]),
            started_at=started_at,
            completed_at=completed_at,
        )
        for domain in DOMAINS
    }
    scan = Scan(
        scan_id=scan_id,
        unit_id=unit_id,
        status="complete",
        domain_statuses=domain_statuses,
        findings=findings,
        triggered_at=started_at,
        completed_at=completed_at,
    )
    iris_client.write_findings(scan, findings)
    await _publish_findings(unit_id, findings)
    return scan

