"use client";

import { memo } from "react";

import type { Scan } from "@/types";

function AgentActivityRibbonComponent({ scan }: { scan: Scan | null }) {
  const entries = scan ? Object.entries(scan.domain_statuses) : [];

  return (
    <div className="panel ribbon">
      <div>
        <div className="eyebrow">Agent Activity Ribbon</div>
        <h3 style={{ margin: "8px 0 0" }}>Live domain progress and finding stream</h3>
      </div>
      <div className="progress-row">
        {entries.map(([domain, status]) => (
          <div className="progress-tile" key={domain}>
            <strong>{domain}</strong>
            <div className="muted">{status.status}</div>
            <div>{status.finding_count} findings</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export const AgentActivityRibbon = memo(AgentActivityRibbonComponent);
