"use client";

import { useEffect, useRef, useState } from "react";
import { useShallow } from "zustand/shallow";

import { AgentActivityRibbon } from "@/components/findings/AgentActivityRibbon";
import { FindingFeed } from "@/components/findings/FindingFeed";
import { WorldViewer } from "@/components/viewer/WorldViewer";
import { api } from "@/lib/api";
import { useScanStream } from "@/hooks/useScanStream";
import { useSplatModel } from "@/hooks/useSplatModel";
import { useStore } from "@/store";
import type { Scan } from "@/types";

function scanMatchesModel(scan: Scan | null, modelId: string | null | undefined): boolean {
  return Boolean(scan && modelId && scan.model_id === modelId);
}

export function ModelClient({
  facilityId,
  unitId,
  initialScan
}: {
  facilityId: string;
  unitId: string;
  initialScan: Scan | null;
}) {
  const { findings, setFindings } = useStore(
    useShallow((state) => ({
      findings: state.findings,
      setFindings: state.setFindings,
    })),
  );
  const { signedUrl, status, loading, error } = useSplatModel(unitId);
  const handledModelId = useRef<string | null>(null);
  const [scan, setScan] = useState<Scan | null>(initialScan);
  const [sceneGraph, setSceneGraph] = useState<Record<string, unknown> | null>(null);

  useScanStream(unitId);

  useEffect(() => {
    if (status?.status !== "ready") {
      setSceneGraph(null);
      return;
    }

    let cancelled = false;
    void api.getSceneGraph(unitId)
      .then((graph) => {
        if (!cancelled) {
          setSceneGraph(graph);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSceneGraph(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [status?.model_id, status?.status, unitId]);

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
        <WorldViewer
          unitId={unitId}
          initialSplatUrl={signedUrl}
          findings={findings}
          sceneGraph={sceneGraph}
          autoRunScan={false}
          brandSubtitle={`Facility ${facilityId} · Unit ${unitId} · Live scan`}
          ctaHref={`/facility/${facilityId}`}
          ctaLabel="Open facility →"
          viewportHeight={720}
        />
        <FindingFeed />
      </div>
      <AgentActivityRibbon scan={scan} />
    </div>
  );
}
