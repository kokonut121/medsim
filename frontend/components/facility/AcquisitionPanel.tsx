"use client";

import type { Route } from "next";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ModelStatusResponse } from "@/types";

const ACTIVE_STATUSES = new Set(["queued", "acquiring", "classifying", "generating"]);

export function AcquisitionPanel({
  facilityId,
  unitId,
  initialStatus
}: {
  facilityId: string;
  unitId: string;
  initialStatus: ModelStatusResponse | null;
}) {
  const [status, setStatus] = useState<ModelStatusResponse | null>(initialStatus);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!status || !ACTIVE_STATUSES.has(status.status)) {
      return;
    }

    const interval = window.setInterval(async () => {
      try {
        const nextStatus = await api.getModelStatus(unitId);
        setStatus(nextStatus);
      } catch {
        // Keep the most recent visible status during polling retries.
      }
    }, 3000);

    return () => window.clearInterval(interval);
  }, [status, unitId]);

  async function startAcquisition() {
    setLoading(true);
    setError(null);
    try {
      const result = (await api.triggerAcquisition(facilityId)) as { model_id: string; status: "queued" };
      setStatus({
        unit_id: unitId,
        model_id: result.model_id,
        status: result.status,
        failure_reason: null,
        source_image_count: 0,
        caption: null,
        thumbnail_url: null,
        world_marble_url: null,
        completed_at: null
      });
    } catch (triggerError) {
      setError(triggerError instanceof Error ? triggerError.message : "Unable to start acquisition");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel" style={{ display: "grid", gap: 14 }}>
      <div>
        <div className="eyebrow">Phase 1 Acquisition</div>
        <h2 style={{ margin: "8px 0 10px" }}>Public imagery to world model</h2>
        <p className="muted" style={{ marginBottom: 0 }}>
          Fetch Google Street View, Places photos, and OSM context, then generate a world model for this unit.
        </p>
      </div>
      <div className="cta-row">
        <button className="button" disabled={loading || (status ? ACTIVE_STATUSES.has(status.status) : false)} onClick={startAcquisition}>
          {loading ? "Launching..." : "Start acquisition"}
        </button>
        <Link className="button secondary" href={`/facility/${facilityId}/model/${unitId}` as Route}>
          Open viewer
        </Link>
      </div>
      <div className="progress-tile">
        <strong>Model status</strong>
        <div className="muted">{status?.status ?? "not started"}</div>
        <div>{status?.source_image_count ?? 0} source images</div>
        {status?.caption ? <div className="muted">{status.caption}</div> : null}
        {status?.failure_reason ? (
          <div className="muted" style={{ color: "var(--critical)" }}>
            {status.failure_reason}
          </div>
        ) : null}
        {status?.world_marble_url ? (
          <a className="button secondary" href={status.world_marble_url} style={{ marginTop: 12, width: "fit-content" }} target="_blank">
            Open in Marble
          </a>
        ) : null}
      </div>
      {error ? (
        <p className="muted" style={{ margin: 0, color: "var(--critical)" }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
