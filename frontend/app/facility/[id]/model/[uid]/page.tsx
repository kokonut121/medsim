import type { Route } from "next";

import { ModelClient } from "./ModelClient";

import { BackLink } from "@/components/ui/BackLink";
import { api } from "@/lib/api";
import type { Scan } from "@/types";

export default async function ModelPage({
  params
}: {
  params: Promise<{ id: string; uid: string }>;
}) {
  const { id, uid } = await params;
  let initialScan: Scan | null = null;
  try {
    initialScan = await api.getScanStatus(uid);
  } catch {
    initialScan = null;
  }

  return (
    <main className="shell shell-dark">
      <BackLink href={`/facility/${id}` as Route} label="Hub" />
      <div className="panel">
        <div className="eyebrow">Facility {id}</div>
        <h1 className="page-title">World model viewer</h1>
        <p className="muted">3D splat canvas, finding feed, and real-time scan ribbon for unit {uid}.</p>
      </div>
      <div style={{ height: 20 }} />
      <ModelClient unitId={uid} initialScan={initialScan} />
    </main>
  );
}

