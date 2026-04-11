import type { Route } from "next";

import { SimulationClient } from "./SimulationClient";

import { BackLink } from "@/components/ui/BackLink";
import { api } from "@/lib/api";
import type { ScenarioSimulation } from "@/types";

export default async function SimulationPage({
  params
}: {
  params: Promise<{ id: string; uid: string }>;
}) {
  const { id, uid } = await params;
  let initialSimulation: ScenarioSimulation | null = null;
  try {
    initialSimulation = await api.getLatestSimulation(uid);
  } catch {
    initialSimulation = null;
  }

  return (
    <main className="shell shell-dark">
      <BackLink href={`/facility/${id}` as Route} label="Hub" />
      <div className="panel">
        <div className="eyebrow">Facility {id}</div>
        <h1 className="page-title">Scenario simulation</h1>
        <p className="muted">
          Swarm a crisis scenario across the trauma center for unit {uid}. Role-playing agents walk
          the floor plan in parallel while a supervising reasoner distills a tactical best plan.
        </p>
      </div>
      <div style={{ height: 20 }} />
      <SimulationClient unitId={uid} initialSimulation={initialSimulation} />
    </main>
  );
}
