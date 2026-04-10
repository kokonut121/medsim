import type { Route } from "next";
import Link from "next/link";

import { AcquisitionPanel } from "@/components/facility/AcquisitionPanel";
import { api } from "@/lib/api";

export default async function FacilityDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await api.getFacility(id);

  return (
    <main className="shell">
      <div className="panel">
        <div className="eyebrow">{data.facility.address}</div>
        <h1 className="page-title">{data.facility.name}</h1>
        <p className="muted">
          Unit list, scan history, and launch points for coverage review, 3D world model inspection, and exports.
        </p>
      </div>
      <div style={{ height: 20 }} />
      <div className="card-grid">
        {data.units.map((unit) => {
          const latestModel = data.models.find((model) => model.unit_id === unit.unit_id) ?? null;

          return (
            <div className="feed-card" key={unit.unit_id}>
              <div className="eyebrow">
                Floor {unit.floor} · {unit.unit_type}
              </div>
              <h3>{unit.name}</h3>
              <div className="cta-row">
                <Link className="button secondary" href={`/facility/${id}/coverage` as Route}>
                  Coverage
                </Link>
                <Link className="button" href={`/facility/${id}/model/${unit.unit_id}` as Route}>
                  Open model
                </Link>
                <Link className="button secondary" href={`/facility/${id}/report/${unit.unit_id}` as Route}>
                  Report
                </Link>
              </div>
              <div style={{ height: 16 }} />
              <AcquisitionPanel
                facilityId={id}
                unitId={unit.unit_id}
                initialStatus={
                  latestModel
                    ? {
                        unit_id: unit.unit_id,
                        model_id: latestModel.model_id,
                        status: latestModel.status,
                        failure_reason: latestModel.failure_reason ?? null,
                        source_image_count: latestModel.source_image_count ?? 0,
                        caption: latestModel.caption ?? null,
                        thumbnail_url: latestModel.thumbnail_url ?? null,
                        world_marble_url: latestModel.world_marble_url ?? null,
                        completed_at: latestModel.completed_at
                      }
                    : null
                }
              />
            </div>
          );
        })}
      </div>
    </main>
  );
}
