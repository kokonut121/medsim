"use client";

import { useStore } from "@/store";
import type { ScenarioAgentTrace } from "@/types";

const KIND_LABELS: Record<string, string> = {
  incident_commander: "Incident Commander",
  triage_officer: "Triage Officer",
  burn_specialist: "Burn Specialist",
  trauma_surgeon: "Trauma Surgeon",
  anesthesiologist: "Anesthesiologist",
  resource_allocator: "Resource Allocator",
  scenario_patient: "Patient",
  nurse: "Nurse",
  doctor: "Doctor"
};

function TraceCard({ trace }: { trace: ScenarioAgentTrace }) {
  return (
    <div className="feed-card" style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
        <div>
          <div className="eyebrow">#{trace.agent_index} · {KIND_LABELS[trace.kind] ?? trace.kind}</div>
          <strong>{trace.role_label}</strong>
        </div>
        <div className="muted" style={{ fontSize: 12, textAlign: "right" }}>
          efficiency<br />
          <strong style={{ fontSize: 16 }}>{trace.efficiency_score.toFixed(1)}</strong>
        </div>
      </div>

      {trace.path.length > 0 && (
        <div className="muted" style={{ fontSize: 12 }}>
          <span style={{ textTransform: "uppercase", letterSpacing: 0.5 }}>Path · </span>
          {trace.path.join(" → ")}
        </div>
      )}

      {trace.actions.length > 0 && (
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
          {trace.actions.slice(0, 4).map((action, index) => (
            <li key={index}>{action}</li>
          ))}
        </ul>
      )}

      {trace.bottlenecks.length > 0 && (
        <div style={{ fontSize: 12 }}>
          <span className="muted">Bottlenecks: </span>
          {trace.bottlenecks.join(", ")}
        </div>
      )}

      {trace.resource_needs.length > 0 && (
        <div style={{ fontSize: 12 }}>
          <span className="muted">Needs: </span>
          {trace.resource_needs.join(", ")}
        </div>
      )}

      {trace.patient_tags.length > 0 && (
        <div style={{ display: "flex", gap: 6 }}>
          {trace.patient_tags.map((tag) => (
            <span
              key={tag}
              style={{
                fontSize: 11,
                padding: "2px 8px",
                borderRadius: 999,
                background: "rgba(255,255,255,0.08)",
                textTransform: "uppercase",
                letterSpacing: 0.5
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {trace.notes && (
        <div className="muted" style={{ fontSize: 12, fontStyle: "italic" }}>
          {trace.notes}
        </div>
      )}
    </div>
  );
}

export function AgentTraceFeed() {
  const traces = useStore((state) => state.simulationTraces);
  const sorted = [...traces].sort((a, b) => a.agent_index - b.agent_index);

  return (
    <div className="panel" style={{ display: "grid", gap: 14 }}>
      <div>
        <div className="eyebrow">Live swarm</div>
        <h2 style={{ margin: "8px 0 4px" }}>Agent traces</h2>
        <p className="muted" style={{ margin: 0, fontSize: 12 }}>
          {traces.length} agent{traces.length === 1 ? "" : "s"} reporting in
        </p>
      </div>
      {sorted.length === 0 ? (
        <div className="muted" style={{ fontSize: 13 }}>
          Waiting for the first agent to return…
        </div>
      ) : (
        <div style={{ display: "grid", gap: 12, maxHeight: 520, overflowY: "auto" }}>
          {sorted.map((trace) => (
            <TraceCard key={`${trace.kind}-${trace.agent_index}`} trace={trace} />
          ))}
        </div>
      )}
    </div>
  );
}
