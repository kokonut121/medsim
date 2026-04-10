"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useShallow } from "zustand/shallow";

import { AgentActivityRibbon } from "@/components/findings/AgentActivityRibbon";
import { FindingFeed } from "@/components/findings/FindingFeed";
import { SplatRenderer } from "@/components/viewer/SplatRenderer";
import { api } from "@/lib/api";
import { useScanStream } from "@/hooks/useScanStream";
import { useSplatModel } from "@/hooks/useSplatModel";
import { useStore } from "@/store";
import type { Scan } from "@/types";

export function ModelClient({ unitId, initialScan }: { unitId: string; initialScan: Scan | null }) {
  const { findings, selectedFindingId, setFindings } = useStore(
    useShallow((state) => ({
      findings: state.findings,
      selectedFindingId: state.selectedFindingId,
      setFindings: state.setFindings,
    })),
  );
  const { signedUrl, status, loading, error } = useSplatModel(unitId);
  const triggeredScan = useRef(false);
  const [scan, setScan] = useState<Scan | null>(initialScan);

  useScanStream(unitId);

  useEffect(() => {
    if (status?.status !== "ready" || triggeredScan.current) {
      return;
    }
    if (initialScan) {
      setFindings(initialScan.findings);
      setScan(initialScan);
      triggeredScan.current = true;
      return;
    }
    triggeredScan.current = true;
    void api.runScan(unitId).then((nextScan) => {
      setFindings(nextScan.findings);
      setScan(nextScan);
    });
  }, [initialScan, setFindings, status?.status, unitId]);

  const selectedLabel = useMemo(
    () => findings.find((finding) => finding.finding_id === selectedFindingId)?.label_text ?? null,
    [findings, selectedFindingId]
  );

  return (
    <div style={{ display: "grid", gap: 20 }}>
      {status?.status !== "ready" ? (
        <div className="panel">
          <div className="eyebrow">Model generation</div>
          <h2 style={{ margin: "8px 0 10px" }}>{loading ? "Checking model state..." : `Status: ${status?.status ?? "unknown"}`}</h2>
          <p className="muted" style={{ marginBottom: 0 }}>
            {status?.failure_reason ?? error ?? "The viewer will activate automatically once the world model is ready."}
          </p>
        </div>
      ) : null}
      <div className="viewer-layout">
        <SplatRenderer signedUrl={signedUrl} findings={findings} selectedLabel={selectedLabel} />
        <FindingFeed />
      </div>
      <AgentActivityRibbon scan={scan} />
    </div>
  );
}
