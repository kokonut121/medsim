"use client";

import { create } from "zustand";

import type {
  Domain,
  Finding,
  ScenarioAgentEvent,
  ScenarioAgentTrace,
  ScenarioGraphSnapshot,
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
  reasoningGraph: ScenarioGraphSnapshot | null;
  currentSimulation: ScenarioSimulation | null;
  setSimulationStatus: (status: SimulationStatus | null) => void;
  addSimulationTrace: (trace: ScenarioAgentTrace) => void;
  applyAgentEvent: (event: ScenarioAgentEvent) => void;
  appendReasoningChunk: (chunk: string) => void;
  setReasoningGraph: (graph: ScenarioGraphSnapshot | null) => void;
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
  reasoningGraph: null,
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
  applyAgentEvent: (event) =>
    set((state) => {
      const matchById = (existing: ScenarioAgentTrace) =>
        (event.agent_id !== "" && existing.agent_id === event.agent_id) ||
        (existing.agent_index === event.agent_index && existing.kind === event.agent_kind);

      const existingIndex = state.simulationTraces.findIndex(matchById);
      const base: ScenarioAgentTrace =
        existingIndex >= 0
          ? state.simulationTraces[existingIndex]
          : {
              agent_index: event.agent_index,
              agent_id: event.agent_id,
              call_sign: event.call_sign || event.agent_id,
              kind: event.agent_kind,
              role_label: event.role_label || event.agent_kind,
              focus_room_id: null,
              actions: [],
              path: [],
              bottlenecks: [],
              resource_needs: [],
              patient_tags: [],
              tasks: [],
              handoffs: [],
              challenges: [],
              notes: "",
              efficiency_score: 5
            };

      const next: ScenarioAgentTrace = { ...base };
      if (event.kind === "focus") {
        next.focus_room_id = event.focus_room_id;
        next.path = [...event.path];
        next.actions = [...event.actions];
        next.bottlenecks = [...event.bottlenecks];
        next.resource_needs = [...event.resource_needs];
        next.patient_tags = [...event.patient_tags];
      } else if (event.kind === "task" && event.task) {
        next.tasks = [...next.tasks, event.task];
      } else if (event.kind === "handoff" && event.handoff) {
        next.handoffs = [...next.handoffs, event.handoff];
      } else if (event.kind === "challenge" && event.challenge) {
        next.challenges = [...next.challenges, event.challenge];
      } else if (event.kind === "note" && event.note !== null) {
        next.notes = event.note;
      } else if (event.kind === "done" && event.efficiency_score !== null) {
        next.efficiency_score = event.efficiency_score;
      }

      return {
        simulationTraces: upsertBy(state.simulationTraces, next, matchById)
      };
    }),
  appendReasoningChunk: (chunk) =>
    set((state) => ({ reasoningBuffer: state.reasoningBuffer + chunk })),
  setReasoningGraph: (reasoningGraph) => set({ reasoningGraph }),
  setCurrentSimulation: (currentSimulation) => set({ currentSimulation }),
  resetSimulation: () =>
    set({
      simulationStatus: null,
      simulationTraces: [],
      reasoningBuffer: "",
      reasoningGraph: null,
      currentSimulation: null
    })
}));
