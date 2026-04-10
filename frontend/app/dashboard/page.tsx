import type { Route } from "next";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Facility } from "@/types";

function FacilityCard({ facility }: { facility: Facility }) {
  return (
    <Link className="feed-card" href={`/facility/${facility.facility_id}` as Route}>
      <div className="eyebrow">{facility.address}</div>
      <h3 style={{ margin: "6px 0 8px" }}>{facility.name}</h3>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        Acquire imagery → build world model → deploy safety agent teams.
      </p>
    </Link>
  );
}

export default async function DashboardPage() {
  try {
    const facilities = await api.listFacilities();

    return (
      <main className="shell">
        <div className="panel">
          <div className="eyebrow">Dashboard</div>
          <h1 className="page-title">Facility intelligence network</h1>
          <p className="muted">
            Select a facility to view its world model, coverage, findings, and reports.
          </p>
          <div className="card-grid" style={{ marginTop: 24 }}>
            {facilities.map((f) => (
              <FacilityCard key={f.facility_id} facility={f} />
            ))}
          </div>
          {facilities.length === 0 && (
            <p className="muted" style={{ marginTop: 16 }}>
              No facilities yet — add one from the onboarding form.
            </p>
          )}
        </div>
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
            Start the backend with <code>./scripts/start-backend.sh</code> and refresh.
          </p>
          <p className="muted" style={{ marginBottom: 0 }}>{message}</p>
        </div>
      </main>
    );
  }
}
