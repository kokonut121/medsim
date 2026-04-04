from backend.agents.consensus import consensus_synthesis_engine


def test_consensus_promotes_compound_severity_to_critical():
    results = [
        [
            {
                "domain": "ICA",
                "severity": "HIGH",
                "severity_score": 0.7,
                "confidence": 0.8,
                "spatial_anchor": {"x": 0, "y": 0, "z": 0},
            }
        ],
        [
            {
                "domain": "ERA",
                "severity": "HIGH",
                "severity_score": 0.7,
                "confidence": 0.9,
                "spatial_anchor": {"x": 1, "y": 1, "z": 1},
            }
        ],
    ]

    synthesized = consensus_synthesis_engine(results)

    assert len(synthesized) == 1
    assert synthesized[0]["severity"] == "CRITICAL"
    assert synthesized[0]["compound_severity"] >= 0.85

