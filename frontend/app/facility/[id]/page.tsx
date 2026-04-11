import type { Route } from "next";
import Link from "next/link";

import { BackLink } from "@/components/ui/BackLink";
import { api } from "@/lib/api";
import type { WorldModel } from "@/types";

function ModelInfoCard({ model }: { model: WorldModel | null }) {
  if (!model) {
    return (
      <div className="progress-tile" style={{ marginTop: 12 }}>
        <span className="muted">No world model yet.</span>
      </div>
    );
  }

  const statusColor =
    model.status === "ready"
      ? "var(--gain)"
      : model.status === "failed"
      ? "var(--critical)"
      : "var(--muted)";

  return (
    <div className="progress-tile" style={{ marginTop: 12, display: "grid", gap: 6 }}>
      {model.caption ? (
        <p style={{ margin: 0, fontSize: 13 }}>{model.caption}</p>
      ) : null}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12 }}>
        <span>
          Status&nbsp;
          <strong style={{ color: statusColor }}>{model.status}</strong>
        </span>
        {model.source_image_count ? (
          <span className="muted">{model.source_image_count} source images</span>
        ) : null}
        {model.completed_at ? (
          <span className="muted">
            Built {new Date(model.completed_at).toLocaleDateString()}
          </span>
        ) : null}
      </div>
      {model.failure_reason ? (
        <p style={{ margin: 0, fontSize: 12, color: "var(--critical)" }}>
          {model.failure_reason}
        </p>
      ) : null}
    </div>
  );
}

export default async function FacilityDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await api.getFacility(id);

  return (
    <main className="shell">
      <BackLink href="/dashboard" label="Hub" />
      <div className="panel">
        <div className="eyebrow">{data.facility.address}</div>
        <h1 className="page-title">{data.facility.name}</h1>
        <p className="muted">
          Live safety analysis, 3D world model inspection, scenario simulation, and compliance reports.
        </p>
      </div>
      <div style={{ height: 20 }} />
      <div className="card-grid">
        {data.units.map((unit) => {
          const latestModel = data.models.find((m) => m.unit_id === unit.unit_id) ?? null;

          return (
            <div className="feed-card" key={unit.unit_id}>
              <div className="eyebrow">
                Floor {unit.floor} · {unit.unit_type}
              </div>
              <h3 style={{ margin: "6px 0 4px" }}>{unit.name}</h3>
              <ModelInfoCard model={latestModel} />
              <div style={{ height: 16 }} />
              <div className="cta-row">
                <Link className="button" href={`/facility/${id}/model/${unit.unit_id}` as Route}>
                  Open model
                </Link>
                <Link className="button secondary" href={`/facility/${id}/simulation/${unit.unit_id}` as Route}>
                  Simulate crisis
                </Link>
                <Link className="button secondary" href={`/facility/${id}/report/${unit.unit_id}` as Route}>
                  Report
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </main>
  );
}
