"use client";

import { DOMAIN_COLORS } from "@/lib/constants";
import { useStore } from "@/store";
import type { Finding } from "@/types";

export function FindingCard({ finding }: { finding: Finding }) {
  const selectFinding = useStore((state) => state.selectFinding);
  return (
    <button
      className="finding-card"
      onClick={() => selectFinding(finding.finding_id)}
      style={{ width: "100%", textAlign: "left" }}
    >
      <div className="eyebrow" style={{ color: DOMAIN_COLORS[finding.domain] }}>
        {finding.domain} · {finding.severity}
      </div>
      <h3 style={{ margin: "6px 0 10px" }}>{finding.label_text}</h3>
      <p className="muted" style={{ margin: 0 }}>
        {finding.room_id} · confidence {Math.round(finding.confidence * 100)}%
      </p>
      <p style={{ marginBottom: 0 }}>{finding.recommendation}</p>
    </button>
  );
}

