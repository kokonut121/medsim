import { FacilityMap } from "@/components/facility/FacilityMap";
import { api } from "@/lib/api";

export default async function DashboardPage() {
  try {
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
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load facilities.";

    return (
      <main className="shell">
        <div className="panel">
          <div className="eyebrow">Dashboard</div>
          <h1 className="page-title">Backend unavailable</h1>
          <p className="muted">
            The frontend could not reach the FastAPI server. Start the backend from the repo root with
            {" "}
            <code>./scripts/start-backend.sh</code>
            {" "}
            and refresh the page.
          </p>
          <p className="muted" style={{ marginBottom: 0 }}>
            {message}
          </p>
        </div>
      </main>
    );
  }
}
