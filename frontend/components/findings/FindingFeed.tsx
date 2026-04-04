"use client";

import { DomainFilterBar } from "@/components/findings/DomainFilterBar";
import { FindingCard } from "@/components/findings/FindingCard";
import { useStore } from "@/store";

export function FindingFeed() {
  const findings = useStore((state) => state.findings);
  const activeDomains = useStore((state) => state.activeDomains);
  const severityThreshold = useStore((state) => state.severityThreshold);
  const setSeverityThreshold = useStore((state) => state.setSeverityThreshold);

  const filtered = findings.filter(
    (finding) => activeDomains.includes(finding.domain) && finding.compound_severity >= severityThreshold
  );

  return (
    <div className="panel" style={{ display: "grid", gap: 16 }}>
      <div>
        <div className="eyebrow">Finding Feed</div>
        <h2 style={{ margin: "8px 0 10px" }}>Spatially anchored findings</h2>
      </div>
      <DomainFilterBar />
      <label className="muted">
        Severity threshold {severityThreshold.toFixed(2)}
        <input
          style={{ display: "block", width: "100%" }}
          type="range"
          min="0.4"
          max="1"
          step="0.05"
          value={severityThreshold}
          onChange={(event) => setSeverityThreshold(Number(event.target.value))}
        />
      </label>
      <div style={{ display: "grid", gap: 12 }}>
        {filtered.map((finding) => (
          <FindingCard key={finding.finding_id} finding={finding} />
        ))}
      </div>
    </div>
  );
}

