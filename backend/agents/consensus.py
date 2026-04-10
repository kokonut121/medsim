from __future__ import annotations

from math import dist


SEVERITY_SCORES = {"CRITICAL": 1.0, "HIGH": 0.7, "ADVISORY": 0.4}


def _cluster_by_spatial_anchor(findings: list[dict], radius: float) -> list[list[dict]]:
    clusters: list[list[dict]] = []
    for finding in findings:
        point = (
            finding["spatial_anchor"]["x"],
            finding["spatial_anchor"]["y"],
            finding["spatial_anchor"]["z"],
        )
        placed = False
        for cluster in clusters:
            anchor = cluster[0]["spatial_anchor"]
            center = (anchor["x"], anchor["y"], anchor["z"])
            if dist(point, center) <= radius:
                cluster.append(finding)
                placed = True
                break
        if not placed:
            clusters.append([finding])
    return clusters


def consensus_synthesis_engine(team_results: list[list[dict]]) -> list[dict]:
    all_findings = [finding for team in team_results for finding in team]
    # Radius = 0.5 world units ≈ slightly less than one grid cell (GRID_SCALE=0.8).
    # Only findings in the same room (same grid position) get merged; adjacent
    # rooms remain separate findings so nothing collapses across the whole scene.
    location_groups = _cluster_by_spatial_anchor(all_findings, radius=0.5)

    synthesized = []
    for group in location_groups:
        domains = list({finding["domain"] for finding in group})
        max_severity = max(finding["severity_score"] for finding in group)
        compound_severity = min(1.0, max_severity + 0.15 * len(domains))
        confidences = sorted((finding["confidence"] for finding in group), reverse=True)
        tail_average = sum(confidences[1:]) / max(len(confidences[1:]), 1)
        weighted_confidence = 0.5 * confidences[0] + 0.5 * tail_average
        lead = max(group, key=lambda finding: finding["confidence"])
        synthesized.append(
            {
                **lead,
                "compound_severity": compound_severity,
                "severity": "CRITICAL" if compound_severity >= 0.85 else lead["severity"],
                "compound_domains": domains,
                "confidence": weighted_confidence,
            }
        )
    return sorted(synthesized, key=lambda finding: finding["compound_severity"], reverse=True)

