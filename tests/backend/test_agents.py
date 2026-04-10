"""
Tests for all six domain agent teams and the scan orchestrator.
All tests use synthetic fallbacks — no live API keys required.
"""
from __future__ import annotations

import asyncio

import pytest

from backend.agents import era_team, fra_team, ica_team, msa_team, pfa_team, sca_team
from backend.agents.orchestrator import run_scan


TEAMS = [ica_team, msa_team, fra_team, era_team, pfa_team, sca_team]
EXPECTED_DOMAINS = ["ICA", "MSA", "FRA", "ERA", "PFA", "SCA"]


# ---------------------------------------------------------------------------
# Individual agent teams
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("team, expected_domain", zip(TEAMS, EXPECTED_DOMAINS))
def test_team_returns_findings(team, expected_domain, demo_world_model):
    findings = asyncio.get_event_loop().run_until_complete(
        team.run("scan_test", demo_world_model)
    )
    assert isinstance(findings, list)
    assert len(findings) >= 1


@pytest.mark.parametrize("team, expected_domain", zip(TEAMS, EXPECTED_DOMAINS))
def test_team_finding_schema(team, expected_domain, demo_world_model):
    """Every finding must carry the required keys with correct types."""
    findings = asyncio.get_event_loop().run_until_complete(
        team.run("scan_schema_check", demo_world_model)
    )
    for f in findings:
        assert f["domain"] == expected_domain
        assert f["severity"] in ("CRITICAL", "HIGH", "ADVISORY")
        assert 0.0 <= f["confidence"] <= 1.0
        assert 0.0 <= f["compound_severity"] <= 1.0
        assert isinstance(f["spatial_anchor"], dict)
        assert {"x", "y", "z"} <= f["spatial_anchor"].keys()
        assert isinstance(f["label_text"], str) and f["label_text"]
        assert isinstance(f["recommendation"], str) and f["recommendation"]


@pytest.mark.parametrize("team, expected_domain", zip(TEAMS, EXPECTED_DOMAINS))
def test_team_finding_bound_to_scan_id(team, expected_domain, demo_world_model):
    scan_id = "scan_binding_test"
    findings = asyncio.get_event_loop().run_until_complete(
        team.run(scan_id, demo_world_model)
    )
    for f in findings:
        assert f["scan_id"] == scan_id


# ---------------------------------------------------------------------------
# Full orchestrator scan (uses seeded demo unit_1)
# ---------------------------------------------------------------------------

def test_run_scan_returns_scan_object(seeded_unit_id):
    scan = asyncio.get_event_loop().run_until_complete(
        run_scan(seeded_unit_id, "model_unit_1")
    )
    assert scan.scan_id.startswith("scan_")
    assert scan.unit_id == seeded_unit_id
    assert scan.status == "complete"


def test_run_scan_covers_all_six_domains(seeded_unit_id):
    scan = asyncio.get_event_loop().run_until_complete(
        run_scan(seeded_unit_id, "model_unit_1")
    )
    domains_in_scan = {f.domain for f in scan.findings}
    assert domains_in_scan == {"ICA", "MSA", "FRA", "ERA", "PFA", "SCA"}


def test_run_scan_domain_statuses_complete(seeded_unit_id):
    scan = asyncio.get_event_loop().run_until_complete(
        run_scan(seeded_unit_id, "model_unit_1")
    )
    for domain, status in scan.domain_statuses.items():
        assert status.status == "complete", f"{domain} did not complete"
        assert status.finding_count >= 1


def test_run_scan_findings_persisted_to_iris(seeded_unit_id):
    from backend.db.iris_client import iris_client
    scan = asyncio.get_event_loop().run_until_complete(
        run_scan(seeded_unit_id, "model_unit_1")
    )
    persisted = iris_client.list_findings(seeded_unit_id)
    finding_ids = {f.finding_id for f in persisted}
    for f in scan.findings:
        assert f.finding_id in finding_ids


def test_run_scan_findings_are_sorted_by_severity(seeded_unit_id):
    scan = asyncio.get_event_loop().run_until_complete(
        run_scan(seeded_unit_id, "model_unit_1")
    )
    scores = [f.compound_severity for f in scan.findings]
    assert scores == sorted(scores, reverse=True)
