"use client";

import { useEffect } from "react";

import { WS_BASE } from "@/lib/runtime";
import { useStore } from "@/store";
import type { ScenarioAgentTrace, SimulationWsEvent } from "@/types";

/**
 * Subscribes to `/ws/simulate/{unit_id}/live` and dispatches events onto the
 * simulation slice of the Zustand store. Parallel to useScanStream but
 * discriminates on the ``type`` field and closes on the terminal ``complete``
 * event rather than relying on an idle timeout.
 */
export function useSimulationStream(unitId: string) {
  const addTrace = useStore((state) => state.addSimulationTrace);
  const applyAgentEvent = useStore((state) => state.applyAgentEvent);
  const appendChunk = useStore((state) => state.appendReasoningChunk);
  const setGraph = useStore((state) => state.setReasoningGraph);
  const setStatus = useStore((state) => state.setSimulationStatus);
  const setCurrent = useStore((state) => state.setCurrentSimulation);

  useEffect(() => {
    if (!unitId) {
      return;
    }
    const ws = new WebSocket(`${WS_BASE}/ws/simulate/${unitId}/live`);

    ws.onmessage = (event) => {
      let payload: SimulationWsEvent;
      try {
        payload = JSON.parse(event.data) as SimulationWsEvent;
      } catch {
        return;
      }
      switch (payload.type) {
        case "status":
          setStatus(payload.status);
          break;
        case "agent_trace": {
          const { type: _type, simulation_id: _sim, ...trace } = payload;
          addTrace(trace as ScenarioAgentTrace);
          break;
        }
        case "agent_event":
          applyAgentEvent(payload.event);
          break;
        case "graph_update":
          setGraph(payload.snapshot);
          break;
        case "reasoning_chunk":
          appendChunk(payload.text);
          break;
        case "complete":
          setCurrent(payload.simulation);
          setStatus(payload.simulation.status);
          setGraph(payload.simulation.reasoning_graph);
          ws.close();
          break;
      }
    };

    return () => ws.close();
  }, [addTrace, applyAgentEvent, appendChunk, setCurrent, setGraph, setStatus, unitId]);
}
