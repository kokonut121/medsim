"use client";

import { create } from "zustand";

import type {
  Domain,
  Finding,
  ScenarioAgentTrace,
  ScenarioSimulation,
  SimulationStatus
} from "@/types";

type StoreState = {
  findings: Finding[];
  activeDomains: Domain[];
  severityThreshold: number;
  selectedFindingId: string | null;
  addFinding: (finding: Finding) => void;
  setFindings: (findings: Finding[]) => void;
  toggleDomain: (domain: Domain) => void;
  setSeverityThreshold: (value: number) => void;
  selectFinding: (findingId: string | null) => void;

  // Scenario simulation slice
  simulationStatus: SimulationStatus | null;
  simulationTraces: ScenarioAgentTrace[];
  reasoningBuffer: string;
  currentSimulation: ScenarioSimulation | null;
  setSimulationStatus: (status: SimulationStatus | null) => void;
  addSimulationTrace: (trace: ScenarioAgentTrace) => void;
  appendReasoningChunk: (chunk: string) => void;
  setCurrentSimulation: (simulation: ScenarioSimulation | null) => void;
  resetSimulation: () => void;
};

const allDomains: Domain[] = ["ICA", "MSA", "FRA", "ERA", "PFA", "SCA"];

function upsertBy<T>(
  items: T[],
  nextItem: T,
  isMatch: (item: T) => boolean,
): T[] {
  const index = items.findIndex(isMatch);

  if (index === -1) {
    return [...items, nextItem];
  }

  if (items[index] === nextItem) {
    return items;
  }

  const nextItems = items.slice();
  nextItems[index] = nextItem;
  return nextItems;
}

export const useStore = create<StoreState>((set) => ({
  findings: [],
  activeDomains: allDomains,
  severityThreshold: 0.4,
  selectedFindingId: null,
  addFinding: (finding) =>
    set((state) => ({
      findings: upsertBy(
        state.findings,
        finding,
        (item) => item.finding_id === finding.finding_id,
      )
    })),
  setFindings: (findings) => set({ findings }),
  toggleDomain: (domain) =>
    set((state) => ({
      activeDomains: state.activeDomains.includes(domain)
        ? state.activeDomains.filter((value) => value !== domain)
        : [...state.activeDomains, domain]
    })),
  setSeverityThreshold: (severityThreshold) => set({ severityThreshold }),
  selectFinding: (selectedFindingId) => set({ selectedFindingId }),

  simulationStatus: null,
  simulationTraces: [],
  reasoningBuffer: "",
  currentSimulation: null,
  setSimulationStatus: (simulationStatus) => set({ simulationStatus }),
  addSimulationTrace: (trace) =>
    set((state) => ({
      simulationTraces: upsertBy(
        state.simulationTraces,
        trace,
        (existing) =>
          existing.agent_index === trace.agent_index &&
          existing.kind === trace.kind,
      )
    })),
  appendReasoningChunk: (chunk) =>
    set((state) => ({ reasoningBuffer: state.reasoningBuffer + chunk })),
  setCurrentSimulation: (currentSimulation) => set({ currentSimulation }),
  resetSimulation: () =>
    set({
      simulationStatus: null,
      simulationTraces: [],
      reasoningBuffer: "",
      currentSimulation: null
    })
}));
