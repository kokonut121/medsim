import Link from "next/link";

import type { Facility } from "@/types";

export function FacilityMap({ facilities }: { facilities: Facility[] }) {
  return (
    <div className="panel">
      <div className="eyebrow">Mapbox Facility Selector</div>
      <h2 style={{ marginTop: 8 }}>Facility overview</h2>
      <div className="map">
        {facilities.map((facility, index) => (
          <div
            className="map-pin"
            key={facility.facility_id}
            style={{ top: `${20 + index * 18}%`, left: `${18 + index * 14}%` }}
            title={facility.name}
          />
        ))}
      </div>
      <div className="card-grid" style={{ marginTop: 20 }}>
        {facilities.map((facility) => (
          <Link className="feed-card" href={`/facility/${facility.facility_id}`} key={facility.facility_id}>
            <div className="eyebrow">{facility.address}</div>
            <h3 style={{ marginBottom: 8 }}>{facility.name}</h3>
            <p className="muted" style={{ margin: 0 }}>
              Auto-acquire imagery, build 3D world model, deploy six safety agent teams.
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}

