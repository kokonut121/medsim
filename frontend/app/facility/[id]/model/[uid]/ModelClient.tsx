"use client";

import { useEffect, useMemo } from "react";

import { AgentActivityRibbon } from "@/components/findings/AgentActivityRibbon";
import { FindingFeed } from "@/components/findings/FindingFeed";
import { SplatRenderer } from "@/components/viewer/SplatRenderer";
import { api } from "@/lib/api";
import { useScanStream } from "@/hooks/useScanStream";
import { useSplatModel } from "@/hooks/useSplatModel";
import { useStore } from "@/store";
import type { Scan } from "@/types";

export function ModelClient({ unitId, initialScan }: { unitId: string; initialScan: Scan | null }) {
  const findings = useStore((state) => state.findings);
  const setFindings = useStore((state) => state.setFindings);
  const selectedFindingId = useStore((state) => state.selectedFindingId);
  const { signedUrl } = useSplatModel(unitId);

  useScanStream(unitId);

  useEffect(() => {
    if (initialScan) {
      setFindings(initialScan.findings);
      return;
    }
    void api.runScan(unitId).then((scan) => setFindings(scan.findings));
  }, [initialScan, setFindings, unitId]);

  const selectedLabel = useMemo(
    () => findings.find((finding) => finding.finding_id === selectedFindingId)?.label_text ?? null,
    [findings, selectedFindingId]
  );

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div className="viewer-layout">
        <SplatRenderer signedUrl={signedUrl} findings={findings} selectedLabel={selectedLabel} />
        <FindingFeed />
      </div>
      <AgentActivityRibbon scan={initialScan} />
    </div>
  );
}

