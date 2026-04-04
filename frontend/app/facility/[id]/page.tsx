import Link from "next/link";

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
        {data.units.map((unit) => (
          <div className="feed-card" key={unit.unit_id}>
            <div className="eyebrow">
              Floor {unit.floor} · {unit.unit_type}
            </div>
            <h3>{unit.name}</h3>
            <div className="cta-row">
              <Link className="button secondary" href={`/facility/${id}/coverage`}>
                Coverage
              </Link>
              <Link className="button" href={`/facility/${id}/model/${unit.unit_id}`}>
                Open model
              </Link>
              <Link className="button secondary" href={`/facility/${id}/report/${unit.unit_id}`}>
                Report
              </Link>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}

