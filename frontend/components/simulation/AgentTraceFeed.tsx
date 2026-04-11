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

function callSignPrefix(callSign: string) {
  return callSign.split("-")[0] ?? callSign;
}

function TraceCard({ trace }: { trace: ScenarioAgentTrace }) {
  return (
    <div className="feed-card" style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
        <div style={{ display: "grid", gap: 8, minWidth: 0 }}>
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              flexWrap: "wrap",
              columnGap: 10,
              rowGap: 6
            }}
          >
            <div className="eyebrow" style={{ marginBottom: 0 }}>
              Agent
            </div>
            <strong style={{ fontSize: 17, lineHeight: 1.05 }}>
              {trace.call_sign || `#${trace.agent_index}`}
            </strong>
            <span className="muted" style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: 0.08 }}>
              {trace.focus_room_id ? trace.focus_room_id.replace(/^NL-/, "") : "unplaced"}
            </span>
          </div>
          <div style={{ fontSize: 13, color: "var(--ink-soft)" }}>{trace.role_label}</div>
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

      {(trace.actions?.length ?? 0) > 0 && (
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
          {trace.actions.slice(0, 4).map((action, index) => (
            <li key={index}>{action}</li>
          ))}
        </ul>
      )}

      {(trace.tasks?.length ?? 0) > 0 && (
        <div style={{ display: "grid", gap: 6 }}>
          <span className="muted" style={{ fontSize: 12 }}>Tasks</span>
          {trace.tasks.slice(0, 3).map((task) => (
            <div key={task.task_id} style={{ fontSize: 12 }}>
              <strong>{task.label}</strong> · {task.status}
              {task.room_id ? ` · ${task.room_id}` : ""}
            </div>
          ))}
        </div>
      )}

      {(trace.bottlenecks?.length ?? 0) > 0 && (
        <div style={{ fontSize: 12 }}>
          <span className="muted">Bottlenecks: </span>
          {trace.bottlenecks.join(", ")}
        </div>
      )}

      {(trace.resource_needs?.length ?? 0) > 0 && (
        <div style={{ fontSize: 12 }}>
          <span className="muted">Needs: </span>
          {trace.resource_needs.join(", ")}
        </div>
      )}

      {(trace.handoffs?.length ?? 0) > 0 && (
        <div style={{ fontSize: 12 }}>
          <span className="muted">Handoffs: </span>
          {trace.handoffs.slice(0, 2).map((handoff) => (
            <span key={`${handoff.target_agent_id}-${handoff.reason}`} style={{ marginRight: 8 }}>
              {(handoff.target_agent_id ?? handoff.target_kind ?? "unassigned")} · {handoff.reason}
            </span>
          ))}
        </div>
      )}

      {trace.challenges.length > 0 && (
        <div style={{ fontSize: 12 }}>
          <span className="muted">Challenges: </span>
          {trace.challenges.slice(0, 2).map((challenge) => (
            <span key={challenge.challenge_id} style={{ marginRight: 8 }}>
              {challenge.label}
              {challenge.blocking ? " (blocking)" : ""}
            </span>
          ))}
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
  const legendItems = Array.from(
    new Map(
      sorted
        .filter((trace) => trace.call_sign)
        .map((trace) => [
          callSignPrefix(trace.call_sign),
          {
            code: callSignPrefix(trace.call_sign),
            label: trace.role_label || KIND_LABELS[trace.kind] || trace.kind
          }
        ])
    ).values()
  );

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
      {legendItems.length > 0 && (
        <div
          style={{
            display: "grid",
            gap: 10,
            paddingTop: 4,
            borderTop: "1px solid rgba(11,16,15,0.10)"
          }}
        >
          <div className="muted" style={{ fontSize: 12 }}>
            Agent code legend
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {legendItems.map((item) => (
              <div
                key={item.code}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "7px 10px",
                  borderRadius: 999,
                  background: "rgba(250,244,228,0.56)",
                  border: "1px solid rgba(11,16,15,0.08)"
                }}
              >
                <strong style={{ fontSize: 12, minWidth: 26 }}>{item.code}</strong>
                <span className="muted" style={{ fontSize: 12 }}>
                  {item.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
