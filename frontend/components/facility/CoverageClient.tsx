"use client";

import { CoverageMap } from "@/components/facility/CoverageMap";
import { SupplementalUpload } from "@/components/facility/SupplementalUpload";
import { useCoverageMap } from "@/hooks/useCoverageMap";

export function CoverageClient({ facilityId }: { facilityId: string }) {
  const coverageMap = useCoverageMap(facilityId);

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <CoverageMap coverageMap={coverageMap} />
      <SupplementalUpload facilityId={facilityId} />
    </div>
  );
}
