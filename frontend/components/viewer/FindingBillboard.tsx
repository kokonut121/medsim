"use client";

import { memo } from "react";

import { DOMAIN_COLORS, SEVERITY_SIZES } from "@/lib/constants";
import type { Finding } from "@/types";

function FindingBillboardComponent({ finding }: { finding: Finding }) {
  const scale = SEVERITY_SIZES[finding.severity];
  const top = `${20 + finding.spatial_anchor.y * 8}%`;
  const left = `${12 + finding.spatial_anchor.x * 4}%`;

  return (
    <div
      className="annotation"
      style={{
        top,
        left,
        background: DOMAIN_COLORS[finding.domain],
        transform: `scale(${scale})`
      }}
    >
      <strong>{finding.domain}</strong>
      <div>{finding.label_text}</div>
    </div>
  );
}

export const FindingBillboard = memo(FindingBillboardComponent);
