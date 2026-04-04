"use client";

import { FindingBillboard } from "@/components/viewer/FindingBillboard";
import type { Finding } from "@/types";

export function AnnotationOverlay({ findings }: { findings: Finding[] }) {
  return (
    <>
      {findings.map((finding) => (
        <FindingBillboard key={finding.finding_id} finding={finding} />
      ))}
    </>
  );
}

