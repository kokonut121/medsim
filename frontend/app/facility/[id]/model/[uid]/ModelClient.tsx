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

function scanMatchesModel(scan: Scan | null, modelId: string | null | undefined): boolean {
  return Boolean(scan && modelId && scan.model_id === modelId);
}

export function ModelClient({ unitId, initialScan }: { unitId: string; initialScan: Scan | null }) {
  const { findings, selectedFindingId, setFindings } = useStore(
    useShallow((state) => ({
      findings: state.findings,
      selectedFindingId: state.selectedFindingId,
      setFindings: state.setFindings,
    })),
  );
  const { signedUrl, status, loading, error } = useSplatModel(unitId);
  const handledModelId = useRef<string | null>(null);
  const [scan, setScan] = useState<Scan | null>(initialScan);

  useScanStream(unitId);

  useEffect(() => {
    if (status?.status !== "ready" || !status.model_id || handledModelId.current === status.model_id) {
      return;
    }
    handledModelId.current = status.model_id;

    let cancelled = false;
    let timeoutId: number | undefined;

    const schedulePoll = () => {
      timeoutId = window.setTimeout(() => {
        void syncScan();
      }, 2000);
    };

    const syncScan = async () => {
      try {
        const latestScan = await api.getScanStatus(unitId);
        if (cancelled || latestScan.model_id !== status.model_id) {
          schedulePoll();
          return;
        }

        setScan(latestScan);

        if (latestScan.status === "complete") {
          setFindings(latestScan.findings);
          return;
        }

        if (latestScan.status !== "failed") {
          schedulePoll();
        }
      } catch {
        if (!cancelled) {
          schedulePoll();
        }
      }
    };

    const matchingInitialScan = scanMatchesModel(initialScan, status.model_id) ? initialScan : null;

    if (matchingInitialScan) {
      setScan(matchingInitialScan);
      if (matchingInitialScan.status === "complete") {
        setFindings(matchingInitialScan.findings);
        return () => {
          cancelled = true;
          if (timeoutId) {
            window.clearTimeout(timeoutId);
          }
        };
      }

      setFindings([]);
      void syncScan();
      return () => {
        cancelled = true;
        if (timeoutId) {
          window.clearTimeout(timeoutId);
        }
      };
    }

    setFindings([]);
    void api.runScan(unitId)
      .then((queuedScan) => {
        if (cancelled) {
          return;
        }
        setScan(queuedScan);
        void syncScan();
      })
      .catch(() => {
        if (!cancelled) {
          setScan(null);
        }
      });

    return () => {
      cancelled = true;
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [initialScan, setFindings, status?.model_id, status?.status, unitId]);

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
