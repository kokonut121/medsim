import type { CoverageMap as CoverageMapType } from "@/types";

export function CoverageMap({ coverageMap }: { coverageMap: CoverageMapType | null }) {
  return (
    <div className="panel">
      <div className="eyebrow">Coverage Map</div>
      <h2 style={{ marginTop: 8 }}>Automatic imagery coverage</h2>
      <div className="coverage-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <div className="feed-card">
          <strong>Covered areas</strong>
          <table>
            <tbody>
              {(coverageMap?.covered_areas ?? []).map((area) => (
                <tr key={area.area_id}>
                  <td>{area.area_id}</td>
                  <td>{area.source}</td>
                  <td>{area.image_count} images</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="feed-card">
          <strong>Gap areas</strong>
          <table>
            <tbody>
              {(coverageMap?.gap_areas ?? []).map((area) => (
                <tr key={area.area_id}>
                  <td>{area.area_id}</td>
                  <td>{area.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

