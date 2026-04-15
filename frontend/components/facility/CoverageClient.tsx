"use client";

import { useEffect, useState } from "react";

import { SupplementalUpload } from "@/components/facility/SupplementalUpload";
import { api } from "@/lib/api";
import type { CoverageMap, FacilityImage } from "@/types";

function formatLabel(value: string | null | undefined): string {
  if (!value) {
    return "Uncategorized";
  }

  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "Awaiting refresh";
  }

  return new Date(value).toLocaleString();
}

export function CoverageClient({ facilityId }: { facilityId: string }) {
  const [coverage, setCoverage] = useState<CoverageMap | null>(null);
  const [images, setImages] = useState<FacilityImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshIndex, setRefreshIndex] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadCoverage() {
      setLoading(true);

      try {
        const [nextCoverage, nextImages] = await Promise.all([
          api.getCoverage(facilityId),
          api.listFacilityImages(facilityId)
        ]);

        if (cancelled) {
          return;
        }

        setCoverage(nextCoverage);
        setImages(nextImages);
        setError(null);
      } catch (loadError) {
        if (cancelled) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : "Unable to load coverage data");
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadCoverage();

    return () => {
      cancelled = true;
    };
  }, [facilityId, refreshIndex]);

  const sourceCounts: Record<string, number> = {};
  const categorySummaries = new Map<
    string,
    { imageCount: number; sources: Set<string>; headingCount: number }
  >();

  for (const image of images) {
    sourceCounts[image.source] = (sourceCounts[image.source] ?? 0) + 1;

    const categoryKey = image.category ?? "uncategorized";
    const summary = categorySummaries.get(categoryKey) ?? {
      imageCount: 0,
      sources: new Set<string>(),
      headingCount: 0
    };

    summary.imageCount += 1;
    summary.sources.add(image.source);
    if (typeof image.heading === "number") {
      summary.headingCount += 1;
    }

    categorySummaries.set(categoryKey, summary);
  }

  const categoryCards = Array.from(categorySummaries.entries())
    .map(([category, summary]) => ({
      category,
      imageCount: summary.imageCount,
      headingCount: summary.headingCount,
      sources: Array.from(summary.sources).sort()
    }))
    .sort((left, right) => right.imageCount - left.imageCount || left.category.localeCompare(right.category));

  const sourceCards = Object.entries(sourceCounts)
    .map(([source, count]) => ({ source, count }))
    .sort((left, right) => right.count - left.count || left.source.localeCompare(right.source));

  const previewImages = images.slice(0, 12);

  return (
    <div className="coverage-grid">
      <div className="panel" style={{ display: "grid", gap: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
          <div>
            <div className="eyebrow">Coverage Signal</div>
            <h2 style={{ margin: "8px 0 10px" }}>Captured imagery versus missing vantage points</h2>
            <p className="muted" style={{ margin: 0 }}>
              Review the represented categories before regenerating the world model, then fill the missing zones with
              targeted uploads from the walkthrough or supplemental photo set.
            </p>
          </div>
          <div style={{ display: "grid", gap: 10, justifyItems: "end" }}>
            <button className="button secondary" type="button" onClick={() => setRefreshIndex((value) => value + 1)}>
              {loading ? "Refreshing..." : "Refresh coverage"}
            </button>
            <div className="muted" style={{ fontSize: 12 }}>
              Last update: {formatTimestamp(coverage?.updated_at ?? null)}
            </div>
          </div>
        </div>

        <div className="stats-grid">
          <div className="progress-tile">
            <strong>{images.length}</strong>
            <div className="muted" style={{ marginTop: 6 }}>
              Source images
            </div>
          </div>
          <div className="progress-tile">
            <strong>{coverage?.covered_areas.length ?? 0}</strong>
            <div className="muted" style={{ marginTop: 6 }}>
              Captured assets in coverage map
            </div>
          </div>
          <div className="progress-tile">
            <strong>{categoryCards.length}</strong>
            <div className="muted" style={{ marginTop: 6 }}>
              Represented imagery categories
            </div>
          </div>
          <div
            className="progress-tile"
            style={{ borderTopColor: (coverage?.gap_areas.length ?? 0) > 0 ? "var(--signal)" : "var(--gain)" }}
          >
            <strong>{coverage?.gap_areas.length ?? 0}</strong>
            <div className="muted" style={{ marginTop: 6 }}>
              Remaining required coverage gaps
            </div>
          </div>
        </div>

        {error ? (
          <p className="muted" style={{ margin: 0, color: "var(--critical)" }}>
            {error}
          </p>
        ) : null}
      </div>

      <div className="card-grid">
        <section className="panel" style={{ display: "grid", gap: 16 }}>
          <div>
            <div className="eyebrow">Missing Coverage</div>
            <h3 style={{ margin: "8px 0 10px" }}>Required categories still needing imagery</h3>
            <p className="muted" style={{ margin: 0 }}>
              These gaps come directly from the backend coverage pass and are the safest targets to fill before another
              generation run.
            </p>
          </div>

          {coverage?.gap_areas.length ? (
            <div style={{ display: "grid", gap: 12 }}>
              {coverage.gap_areas.map((gap) => (
                <div className="progress-tile" key={gap.area_id} style={{ borderTopColor: "var(--signal)" }}>
                  <strong>{formatLabel(gap.area_id)}</strong>
                  <div className="muted" style={{ marginTop: 6 }}>
                    {gap.description}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="progress-tile" style={{ borderTopColor: "var(--gain)" }}>
              <strong>All required categories are represented.</strong>
              <div className="muted" style={{ marginTop: 6 }}>
                You can still upload additional angles if you want denser coverage or better interior continuity.
              </div>
            </div>
          )}
        </section>

        <section className="panel" style={{ display: "grid", gap: 16 }}>
          <div>
            <div className="eyebrow">Captured Categories</div>
            <h3 style={{ margin: "8px 0 10px" }}>What the current image set already covers</h3>
            <p className="muted" style={{ margin: 0 }}>
              Categories with multiple angles and mixed sources generally give the world model generator the best
              chance of reconstructing stable geometry.
            </p>
          </div>

          {categoryCards.length ? (
            <div style={{ display: "grid", gap: 12 }}>
              {categoryCards.map((card) => (
                <div className="progress-tile" key={card.category}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline" }}>
                    <strong>{formatLabel(card.category)}</strong>
                    <span className="muted">{card.imageCount} images</span>
                  </div>
                  <div className="muted" style={{ marginTop: 6 }}>
                    Sources: {card.sources.map(formatLabel).join(", ")}
                  </div>
                  <div className="muted" style={{ marginTop: 4 }}>
                    Directional frames: {card.headingCount}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="progress-tile">
              <strong>No imagery has been cataloged yet.</strong>
              <div className="muted" style={{ marginTop: 6 }}>
                Start acquisition or upload supplemental walkthrough frames to populate the coverage view.
              </div>
            </div>
          )}
        </section>
      </div>

      <div className="card-grid">
        <section className="panel" style={{ display: "grid", gap: 16 }}>
          <div>
            <div className="eyebrow">Acquisition Mix</div>
            <h3 style={{ margin: "8px 0 10px" }}>Current source balance</h3>
            <p className="muted" style={{ margin: 0 }}>
              Mixing walkthrough captures with public imagery usually produces better interior continuity than relying on
              one source alone.
            </p>
          </div>

          {sourceCards.length ? (
            <div className="stats-grid">
              {sourceCards.map((card) => (
                <div className="progress-tile" key={card.source}>
                  <strong>{card.count}</strong>
                  <div className="muted" style={{ marginTop: 6 }}>
                    {formatLabel(card.source)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="progress-tile">
              <strong>No source mix yet.</strong>
              <div className="muted" style={{ marginTop: 6 }}>
                Once images are acquired, this panel will break down how much came from each channel.
              </div>
            </div>
          )}
        </section>

        <section className="panel" style={{ display: "grid", gap: 16 }}>
          <div>
            <div className="eyebrow">Preview Library</div>
            <h3 style={{ margin: "8px 0 10px" }}>First twelve captured frames</h3>
            <p className="muted" style={{ margin: 0 }}>
              Use this as a quick sanity check for exposure, room variety, and whether the walkthrough actually reaches
              the spaces you care about.
            </p>
          </div>

          {previewImages.length ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 14 }}>
              {previewImages.map((image) => (
                <article className="feed-card" key={image.image_id} style={{ padding: 0 }}>
                  <img
                    alt={formatLabel(image.category)}
                    src={image.url}
                    style={{
                      width: "100%",
                      height: 140,
                      objectFit: "cover",
                      borderBottom: "1px solid var(--chalk)"
                    }}
                  />
                  <div style={{ padding: "16px 18px", display: "grid", gap: 6 }}>
                    <strong>{formatLabel(image.category)}</strong>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {formatLabel(image.source)}
                    </div>
                    {typeof image.heading === "number" ? (
                      <div className="muted" style={{ fontSize: 12 }}>
                        Heading {image.heading}°
                      </div>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="progress-tile">
              <strong>No preview images are available yet.</strong>
              <div className="muted" style={{ marginTop: 6 }}>
                This gallery fills in automatically once acquisition or uploads complete.
              </div>
            </div>
          )}
        </section>
      </div>

      <SupplementalUpload facilityId={facilityId} />
    </div>
  );
}
