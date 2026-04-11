"use client";

import { useState } from "react";

import { useStore } from "@/store";
import type { ScenarioAgentTrace } from "@/types";

const KIND_LABEL: Record<string, string> = {
  incident_commander: "Incident Commander",
  triage_officer:     "Triage Officer",
  burn_specialist:    "Burn Specialist",
  trauma_surgeon:     "Trauma Surgeon",
  anesthesiologist:   "Anesthesiologist",
  resource_allocator: "Resource Allocator",
  scenario_patient:   "Patient",
  nurse:              "Nurse",
  doctor:             "Doctor",
};

const KIND_ORDER = [
  "incident_commander",
  "triage_officer",
  "trauma_surgeon",
  "anesthesiologist",
  "burn_specialist",
  "resource_allocator",
  "nurse",
  "doctor",
  "scenario_patient",
];

function shortPath(path: string[] | undefined): string {
  if (!path?.length) return "—";
  if (path.length <= 3) return path.join(" → ");
  return `${path[0]} → … → ${path[path.length - 1]} (${path.length} rooms)`;
}

function EffDot({ score }: { score: number }) {
  const color = score >= 8 ? "#4caf50" : score >= 6 ? "#e6b14a" : "#ff5a5f";
  return (
    <span
      title={`Efficiency ${score.toFixed(1)}`}
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: color,
        flexShrink: 0,
        marginTop: 1,
      }}
    />
  );
}

function AgentRow({ trace }: { trace: ScenarioAgentTrace }) {
  const [open, setOpen] = useState(false);
  const label = trace.call_sign && trace.call_sign !== trace.agent_id
    ? trace.call_sign
    : `#${trace.agent_index}`;
  const topAction = trace.actions?.[0] ?? null;
  const hasDetails =
    (trace.path?.length ?? 0) > 0 ||
    (trace.actions?.length ?? 0) > 1 ||
    (trace.bottlenecks?.length ?? 0) > 0 ||
    (trace.resource_needs?.length ?? 0) > 0 ||
    (trace.challenges?.length ?? 0) > 0 ||
    (trace.tasks?.length ?? 0) > 0 ||
    !!trace.notes;

  return (
    <div
      style={{
        borderRadius: 6,
        background: "rgba(11,16,15,0.04)",
        border: "1px solid rgba(11,16,15,0.07)",
        overflow: "hidden",
      }}
    >
      {/* Summary row */}
      <button
        onClick={() => hasDetails && setOpen((v) => !v)}
        style={{
          all: "unset",
          display: "grid",
          gridTemplateColumns: "8px minmax(0,1fr) auto",
          gap: 10,
          padding: "9px 12px",
          width: "100%",
          cursor: hasDetails ? "pointer" : "default",
          alignItems: "start",
        }}
      >
        <EffDot score={trace.efficiency_score ?? 5} />
        <div style={{ display: "grid", gap: 2 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
            <strong style={{ fontSize: 13 }}>{label}</strong>
            {trace.focus_room_id && (
              <span className="muted" style={{ fontSize: 11 }}>
                {trace.focus_room_id.replace(/^NL-/, "")}
              </span>
            )}
          </div>
          {topAction && (
            <span style={{ fontSize: 12, color: "var(--ink-soft)", lineHeight: 1.4 }}>
              {topAction.length > 80 ? topAction.slice(0, 80) + "…" : topAction}
            </span>
          )}
          {(trace.path?.length ?? 0) > 0 && (
            <span className="muted" style={{ fontSize: 11 }}>
              {shortPath(trace.path)}
            </span>
          )}
        </div>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-soft)", whiteSpace: "nowrap" }}>
          {(trace.efficiency_score ?? 5).toFixed(1)}
        </span>
      </button>

      {/* Expanded details */}
      {open && (
        <div
          style={{
            padding: "0 12px 12px 30px",
            display: "grid",
            gap: 6,
            fontSize: 12,
            borderTop: "1px solid rgba(11,16,15,0.07)",
            paddingTop: 8,
          }}
        >
          {(trace.actions?.length ?? 0) > 1 && (
            <ul style={{ margin: 0, paddingLeft: 16, lineHeight: 1.6 }}>
              {trace.actions.slice(1).map((a, i) => <li key={i}>{a}</li>)}
            </ul>
          )}
          {(trace.tasks?.length ?? 0) > 0 && (
            <div>
              <span className="muted">Tasks: </span>
              {trace.tasks.slice(0, 4).map((t) => (
                <span key={t.task_id} style={{ marginRight: 8 }}>
                  {t.label} <span className="muted">({t.status})</span>
                </span>
              ))}
            </div>
          )}
          {(trace.bottlenecks?.length ?? 0) > 0 && (
            <div><span className="muted">Bottlenecks: </span>{trace.bottlenecks.join(", ")}</div>
          )}
          {(trace.resource_needs?.length ?? 0) > 0 && (
            <div><span className="muted">Needs: </span>{trace.resource_needs.join(", ")}</div>
          )}
          {(trace.challenges?.length ?? 0) > 0 && (
            <div>
              <span className="muted">Challenges: </span>
              {trace.challenges.slice(0, 3).map((c) => (
                <span key={c.challenge_id} style={{ marginRight: 8 }}>
                  {c.label}{c.blocking ? " ⚠" : ""}
                </span>
              ))}
            </div>
          )}
          {(trace.handoffs?.length ?? 0) > 0 && (
            <div>
              <span className="muted">Handoffs: </span>
              {trace.handoffs.slice(0, 2).map((h, i) => (
                <span key={i} style={{ marginRight: 8 }}>
                  {h.target_agent_id ?? h.target_kind ?? "?"} · {h.reason}
                </span>
              ))}
            </div>
          )}
          {trace.notes && (
            <div className="muted" style={{ fontStyle: "italic" }}>{trace.notes}</div>
          )}
        </div>
      )}
    </div>
  );
}

function RoleGroup({ kind, traces }: { kind: string; traces: ScenarioAgentTrace[] }) {
  const [open, setOpen] = useState(true);
  const avgEff = traces.reduce((s, t) => s + (t.efficiency_score ?? 5), 0) / traces.length;
  const label = KIND_LABEL[kind] ?? kind.replace(/_/g, " ");

  return (
    <div style={{ display: "grid", gap: 4 }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          all: "unset",
          display: "flex",
          alignItems: "center",
          gap: 8,
          cursor: "pointer",
          padding: "4px 0",
        }}
      >
        <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
          {label}
        </span>
        <span
          className="muted"
          style={{ fontSize: 11, background: "rgba(11,16,15,0.07)", borderRadius: 999, padding: "1px 7px" }}
        >
          {traces.length}
        </span>
        <span className="muted" style={{ fontSize: 11, marginLeft: "auto" }}>
          avg {avgEff.toFixed(1)} {open ? "▲" : "▼"}
        </span>
      </button>

      {open && (
        <div style={{ display: "grid", gap: 4 }}>
          {traces.map((t) => <AgentRow key={`${t.kind}-${t.agent_index}`} trace={t} />)}
        </div>
      )}
    </div>
  );
}

export function AgentTraceFeed() {
  const traces = useStore((state) => state.simulationTraces);

  // Group by kind, preserving display order
  const groups = new Map<string, ScenarioAgentTrace[]>();
  for (const kind of KIND_ORDER) groups.set(kind, []);
  for (const trace of traces) {
    const key = trace.kind ?? "unknown";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(trace);
  }
  // Sort each group by agent_index
  for (const arr of groups.values()) arr.sort((a, b) => a.agent_index - b.agent_index);
  const filled = [...groups.entries()].filter(([, arr]) => arr.length > 0);

  return (
    <div className="panel" style={{ display: "grid", gap: 14 }}>
      <div>
        <div className="eyebrow">Live swarm</div>
        <h2 style={{ margin: "8px 0 4px" }}>Agent traces</h2>
        <p className="muted" style={{ margin: 0, fontSize: 12 }}>
          {traces.length} agent{traces.length === 1 ? "" : "s"} · {filled.length} role{filled.length === 1 ? "" : "s"} active
        </p>
      </div>

      {filled.length === 0 ? (
        <div className="muted" style={{ fontSize: 13 }}>Waiting for the first agent to return…</div>
      ) : (
        <div style={{ display: "grid", gap: 14, maxHeight: 560, overflowY: "auto" }}>
          {filled.map(([kind, arr]) => (
            <RoleGroup key={kind} kind={kind} traces={arr} />
          ))}
        </div>
      )}
    </div>
  );
}
