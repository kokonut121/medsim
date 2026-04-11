"""
Two-pass consensus engine
=========================
Pass 1 (deterministic): spatial clustering + compound-severity merge
Pass 2 (LLM):           dedupe, wording normalization (OpenAI provider)
Pass 3 (deterministic): schema postchecks, duplicate suppression, severity bounds

Legacy sync entry point `consensus_synthesis_engine` is preserved for
backward compatibility with the startup auto-scan path.
"""
from __future__ import annotations

import json
from math import dist
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agents.providers.base import LLMProvider

SEVERITY_SCORES = {"CRITICAL": 1.0, "HIGH": 0.7, "ADVISORY": 0.4}
_SEVERITY_VALID = {"CRITICAL", "HIGH", "ADVISORY"}


# ---------------------------------------------------------------------------
# Pass 1 — spatial clustering
# ---------------------------------------------------------------------------

def _cluster(findings: list[dict], radius: float) -> list[list[dict]]:
    clusters: list[list[dict]] = []
    for f in findings:
        pt = (f["spatial_anchor"]["x"], f["spatial_anchor"]["y"], f["spatial_anchor"]["z"])
        placed = False
        for cluster in clusters:
            a = cluster[0]["spatial_anchor"]
            if dist(pt, (a["x"], a["y"], a["z"])) <= radius:
                cluster.append(f)
                placed = True
                break
        if not placed:
            clusters.append([f])
    return clusters


def _merge_cluster(group: list[dict]) -> dict:
    domains = list({f["domain"] for f in group})
    max_sev = max(f["severity_score"] for f in group)
    compound = min(1.0, max_sev + 0.15 * len(domains))
    confs = sorted((f["confidence"] for f in group), reverse=True)
    tail = sum(confs[1:]) / max(len(confs[1:]), 1)
    confidence = 0.5 * confs[0] + 0.5 * tail
    lead = max(group, key=lambda f: f["confidence"])
    return {
        **lead,
        "compound_severity": compound,
        "severity": "CRITICAL" if compound >= 0.85 else lead["severity"],
        "compound_domains": domains,
        "confidence": round(confidence, 3),
    }


# ---------------------------------------------------------------------------
# Pass 2 — LLM synthesis
# ---------------------------------------------------------------------------

_SYNTHESIS_SYSTEM = """\
You are a hospital compliance synthesis engine.
Given a list of raw finding candidates (possibly duplicated) from multiple
domain auditors, your job is to:
1. Remove exact or near-duplicate findings (same room, same issue).
2. Merge findings that describe the same problem from different angles.
3. Normalize recommendation wording: concise, actionable, ≤150 chars.
4. Re-rank by clinical priority.

Return ONLY {"findings": [...]} preserving every field from the input.
Do NOT change room_id, spatial_anchor, finding_id, or domain values.
Do NOT add new findings. Do NOT omit required fields.
"""


async def _llm_synthesis(findings: list[dict], provider: "LLMProvider") -> list[dict]:
    if not findings:
        return findings

    # Only send label+recommendation to the LLM — merge back after
    slim = [
        {
            "finding_id": f["finding_id"],
            "domain": f["domain"],
            "room_id": f["room_id"],
            "severity": f["severity"],
            "label_text": f["label_text"],
            "recommendation": f["recommendation"],
        }
        for f in findings
    ]

    user = f"Deduplicate and normalize these {len(slim)} findings:\n{json.dumps(slim)}"

    try:
        result = await provider.complete_json(
            _SYNTHESIS_SYSTEM, user, temperature=0.2, max_tokens=2500,
        )
        synthesized = result.get("findings", slim) if isinstance(result, dict) else slim
    except Exception:
        return findings

    id_to_full = {f["finding_id"]: f for f in findings}
    merged: list[dict] = []
    for s in synthesized:
        fid = s.get("finding_id")
        if fid and fid in id_to_full:
            full = {**id_to_full[fid]}
            full["label_text"] = (s.get("label_text") or full["label_text"])[:120]
            full["recommendation"] = (s.get("recommendation") or full["recommendation"])[:200]
            merged.append(full)

    return merged if merged else findings


# ---------------------------------------------------------------------------
# Pass 3 — deterministic postchecks
# ---------------------------------------------------------------------------

def _postchecks(findings: list[dict], bundle: dict) -> list[dict]:
    room_index = bundle.get("room_index", {})
    seen: set[tuple] = set()
    valid: list[dict] = []

    for f in findings:
        if f.get("room_id") not in room_index:
            continue

        severity = f.get("severity", "ADVISORY")
        if severity not in _SEVERITY_VALID:
            severity = "ADVISORY"
        f["severity"] = severity
        f["severity_score"] = SEVERITY_SCORES[severity]
        compound = float(f.get("compound_severity", SEVERITY_SCORES[severity]))
        f["compound_severity"] = max(0.0, min(1.0, compound))
        conf = float(f.get("confidence", 0.7))
        f["confidence"] = max(0.0, min(1.0, conf))

        key = (f.get("domain", ""), f.get("room_id", ""), f.get("sub_agent", ""))
        if key in seen:
            continue
        seen.add(key)
        valid.append(f)

    return sorted(valid, key=lambda f: f["compound_severity"], reverse=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def consensus_synthesis_engine(team_results: list[list[dict]]) -> list[dict]:
    """Deterministic-only consensus (backward-compat / fallback)."""
    all_findings = [f for team in team_results for f in team]
    groups = _cluster(all_findings, radius=0.5)
    return sorted(
        [_merge_cluster(g) for g in groups],
        key=lambda f: f["compound_severity"],
        reverse=True,
    )


async def agentic_consensus(
    all_findings: list[dict],
    bundle: dict,
    provider: "LLMProvider",
) -> list[dict]:
    """Full three-pass agentic consensus."""
    # Pass 1: spatial merge
    groups = _cluster(all_findings, radius=0.5)
    clustered = [_merge_cluster(g) for g in groups]

    # Pass 2: LLM dedupe/normalize
    synthesized = await _llm_synthesis(clustered, provider)

    # Pass 3: postchecks
    return _postchecks(synthesized, bundle)
