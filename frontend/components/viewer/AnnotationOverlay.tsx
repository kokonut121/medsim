"use client";

import { memo } from "react";

import { FindingBillboard } from "@/components/viewer/FindingBillboard";
import type { Finding } from "@/types";

function AnnotationOverlayComponent({ findings }: { findings: Finding[] }) {
  return (
    <>
      {findings.map((finding) => (
        <FindingBillboard key={finding.finding_id} finding={finding} />
      ))}
    </>
  );
}

export const AnnotationOverlay = memo(AnnotationOverlayComponent);
