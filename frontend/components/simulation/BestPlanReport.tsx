"use client";

import { useState } from "react";

import type { BestPlan, InjurySeverity } from "@/types";

const TIER_ORDER: InjurySeverity[] = ["immediate", "delayed", "minor", "expectant"];
const TIER_COLOR: Record<InjurySeverity, string> = {
  immediate: "#ff5a5f",
  delayed: "#f5a623",
  minor: "#4caf50",
  expectant: "#6b6b6b"
};

function Section({
  title,
  subtitle,
  defaultOpen = true,
  children
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="feed-card" style={{ padding: 0 }}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        style={{
          width: "100%",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "14px 16px",
          background: "transparent",
          border: 0,
          cursor: "pointer",
          color: "inherit",
          textAlign: "left"
        }}
      >
        <div>
          <div className="eyebrow">{subtitle ?? "Report section"}</div>
          <strong style={{ fontSize: 16 }}>{title}</strong>
        </div>
        <span style={{ fontSize: 18 }}>{open ? "−" : "+"}</span>
      </button>
      {open && <div style={{ padding: "0 16px 16px" }}>{children}</div>}
    </div>
  );
}

export function BestPlanReport({ plan }: { plan: BestPlan }) {
  const triageByTier = new Map(plan.triage_priorities.map((entry) => [entry.tier, entry]));

  return (
    <div className="panel" style={{ display: "grid", gap: 14 }}>
      <div>
        <div className="eyebrow">Supervisor report</div>
        <h2 style={{ margin: "8px 0 6px" }}>Best plan</h2>
        <p style={{ margin: 0, fontSize: 14 }}>{plan.summary}</p>
      </div>

      <Section title="Staff placement" subtitle="Section 1 · where people stand" defaultOpen>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "rgba(255,255,255,0.5)" }}>
              <th style={{ padding: "6px 4px" }}>Room</th>
              <th style={{ padding: "6px 4px" }}>Role</th>
              <th style={{ padding: "6px 4px" }}>Count</th>
              <th style={{ padding: "6px 4px" }}>Rationale</th>
            </tr>
          </thead>
          <tbody>
            {plan.staff_placement.map((entry, index) => (
              <tr key={index} style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}>
                <td style={{ padding: "8px 4px", fontFamily: "ui-monospace, monospace" }}>{entry.room_id}</td>
                <td style={{ padding: "8px 4px" }}>{entry.kind}</td>
                <td style={{ padding: "8px 4px" }}>{entry.count}</td>
                <td style={{ padding: "8px 4px", color: "rgba(255,255,255,0.7)" }}>{entry.rationale}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Resource allocation" subtitle="Section 2 · what moves where">
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "rgba(255,255,255,0.5)" }}>
              <th style={{ padding: "6px 4px" }}>Resource</th>
              <th style={{ padding: "6px 4px" }}>From → To</th>
              <th style={{ padding: "6px 4px" }}>Qty</th>
              <th style={{ padding: "6px 4px" }}>Rationale</th>
            </tr>
          </thead>
          <tbody>
            {plan.resource_allocation.map((entry, index) => (
              <tr key={index} style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}>
                <td style={{ padding: "8px 4px" }}>{entry.resource}</td>
                <td style={{ padding: "8px 4px", fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
                  {entry.source_room_id ?? "stock"} → {entry.destination_room_id}
                </td>
                <td style={{ padding: "8px 4px" }}>{entry.quantity}</td>
                <td style={{ padding: "8px 4px", color: "rgba(255,255,255,0.7)" }}>{entry.rationale}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Triage priorities" subtitle="Section 3 · START routing">
        <div style={{ display: "grid", gap: 10 }}>
          {TIER_ORDER.map((tier) => {
            const priority = triageByTier.get(tier);
            if (!priority) return null;
            return (
              <div
                key={tier}
                style={{
                  display: "grid",
                  gap: 6,
                  padding: 12,
                  borderRadius: 6,
                  borderLeft: `4px solid ${TIER_COLOR[tier]}`,
                  background: "rgba(255,255,255,0.04)"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <strong style={{ textTransform: "uppercase", letterSpacing: 0.5 }}>{tier}</strong>
                  <span className="muted" style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
                    → {priority.destination_room_id}
                  </span>
                </div>
                <div style={{ fontSize: 13 }}>{priority.routing_rule}</div>
                {priority.staff_required.length > 0 && (
                  <div style={{ fontSize: 12 }}>
                    <span className="muted">Staff: </span>
                    {priority.staff_required.join(", ")}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Section>

      <Section title="Timeline" subtitle="Section 4 · phased actions">
        <div style={{ display: "grid", gap: 12 }}>
          {plan.timeline.map((phase, index) => (
            <div key={index}>
              <div className="eyebrow">{phase.phase_label}</div>
              {phase.actions.length > 0 && (
                <ul style={{ margin: "6px 0", paddingLeft: 18, fontSize: 13 }}>
                  {phase.actions.map((action, i) => (
                    <li key={i}>{action}</li>
                  ))}
                </ul>
              )}
              {phase.decision_points.length > 0 && (
                <div style={{ fontSize: 12 }}>
                  <span className="muted">Decision points: </span>
                  {phase.decision_points.join(" · ")}
                </div>
              )}
            </div>
          ))}
        </div>
      </Section>

      {plan.assumptions.length > 0 && (
        <div className="muted" style={{ fontSize: 12 }}>
          <strong style={{ textTransform: "uppercase", letterSpacing: 0.5 }}>Assumptions: </strong>
          {plan.assumptions.join(" · ")}
        </div>
      )}
    </div>
  );
}
