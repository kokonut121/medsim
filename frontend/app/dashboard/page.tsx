import { FacilityMap } from "@/components/facility/FacilityMap";
import { api } from "@/lib/api";

export default async function DashboardPage() {
  const facilities = await api.listFacilities();
  return (
    <main className="shell">
      <div className="panel">
        <div className="eyebrow">Dashboard</div>
        <h1 className="page-title">Facility intelligence network</h1>
        <p className="muted">
          Map overview of all facilities, with direct navigation into coverage, model, and report workflows.
        </p>
      </div>
      <div style={{ height: 20 }} />
      <FacilityMap facilities={facilities} />
    </main>
  );
}

