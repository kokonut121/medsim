"use client";

import { create } from "zustand";

import type { Domain, Finding } from "@/types";

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
};

const allDomains: Domain[] = ["ICA", "MSA", "FRA", "ERA", "PFA", "SCA"];

export const useStore = create<StoreState>((set) => ({
  findings: [],
  activeDomains: allDomains,
  severityThreshold: 0.4,
  selectedFindingId: null,
  addFinding: (finding) =>
    set((state) => ({
      findings: [...state.findings.filter((item) => item.finding_id !== finding.finding_id), finding]
    })),
  setFindings: (findings) => set({ findings }),
  toggleDomain: (domain) =>
    set((state) => ({
      activeDomains: state.activeDomains.includes(domain)
        ? state.activeDomains.filter((value) => value !== domain)
        : [...state.activeDomains, domain]
    })),
  setSeverityThreshold: (severityThreshold) => set({ severityThreshold }),
  selectFinding: (selectedFindingId) => set({ selectedFindingId })
}));

