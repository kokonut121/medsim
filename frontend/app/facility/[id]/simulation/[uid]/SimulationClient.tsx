"use client";

import { useEffect, useState } from "react";

import { AgentTraceFeed } from "@/components/simulation/AgentTraceFeed";
import { BestPlanReport } from "@/components/simulation/BestPlanReport";
import { ReasoningStream } from "@/components/simulation/ReasoningStream";
import { ScenarioPromptForm } from "@/components/simulation/ScenarioPromptForm";
import { useSimulationStream } from "@/hooks/useSimulationStream";
import { api } from "@/lib/api";
import { useStore } from "@/store";
import type { ScenarioSimulation, SimulationStatus } from "@/types";

const STATUS_LABELS: Record<SimulationStatus, string> = {
  queued: "Queued",
  running: "Swarm running",
  reasoning: "Supervisor reasoning",
  complete: "Complete",
  failed: "Failed"
};

function StatusBanner({ status, failureReason }: { status: SimulationStatus | null; failureReason: string | null }) {
  if (!status) return null;
  const color =
    status === "failed"
      ? "#ff5a5f"
      : status === "complete"
        ? "#4caf50"
        : "#4ea1ff";
  return (
    <div
      className="panel"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        borderLeft: `4px solid ${color}`,
        padding: "12px 16px"
      }}
    >
      <div
        style={{
          width: 10,
          height: 10,
          borderRadius: 999,
          background: color,
          animation: status === "running" || status === "reasoning" ? "pulse 1.2s ease-in-out infinite" : "none"
        }}
      />
      <div>
        <strong>{STATUS_LABELS[status]}</strong>
        {failureReason && (
          <div className="muted" style={{ fontSize: 12 }}>
            {failureReason}
          </div>
        )}
      </div>
    </div>
  );
}

export function SimulationClient({
  unitId,
  initialSimulation
}: {
  unitId: string;
  initialSimulation: ScenarioSimulation | null;
}) {
  const status = useStore((state) => state.simulationStatus);
  const currentSimulation = useStore((state) => state.currentSimulation);
  const setStatus = useStore((state) => state.setSimulationStatus);
  const setCurrent = useStore((state) => state.setCurrentSimulation);
  const resetSimulation = useStore((state) => state.resetSimulation);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useSimulationStream(unitId);

  // Seed the store from the prefetched latest simulation once on mount.
  useEffect(() => {
    if (initialSimulation) {
      setCurrent(initialSimulation);
      setStatus(initialSimulation.status);
      if (initialSimulation.swarm_aggregate) {
        // Populate the trace feed from the aggregate's traces so revisits show history.
        const addTrace = useStore.getState().addSimulationTrace;
        for (const trace of initialSimulation.swarm_aggregate.traces) {
          addTrace(trace);
        }
      }
    }
  }, [initialSimulation, setCurrent, setStatus]);

  const runningOrPending = status === "queued" || status === "running" || status === "reasoning";
  const plan = currentSimulation?.best_plan ?? null;

  const handleLaunch = async (prompt: string, agentsPerRole: number) => {
    setError(null);
    setLaunching(true);
    resetSimulation();
    try {
      await api.runSimulation(unitId, prompt, agentsPerRole);
      setStatus("queued");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLaunching(false);
    }
  };

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <ScenarioPromptForm disabled={launching || runningOrPending} onSubmit={handleLaunch} />
      {error && (
        <div className="panel" style={{ borderLeft: "4px solid #ff5a5f" }}>
          <strong>Launch failed:</strong> {error}
        </div>
      )}
      <StatusBanner status={status} failureReason={currentSimulation?.failure_reason ?? null} />

      <div
        style={{
          display: "grid",
          gap: 20,
          gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
          alignItems: "start"
        }}
      >
        <AgentTraceFeed />
        <ReasoningStream />
      </div>

      {plan && <BestPlanReport plan={plan} />}

      <style jsx>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
