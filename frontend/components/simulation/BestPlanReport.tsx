"use client";

import { useState } from "react";

import type { BestPlan, InjurySeverity, ScenarioSwarmAggregate } from "@/types";

const TIER_ORDER: InjurySeverity[] = ["immediate", "delayed", "minor", "expectant"];
const TIER_COLOR: Record<InjurySeverity, string> = {
  immediate: "#ff5a5f",
  delayed: "#f5a623",
  minor: "#4caf50",
  expectant: "#6b6b6b"
};

interface WarningItem {
  title: string;
  detail: string;
  mitigation: string;
  severity: "high" | "medium";
}

const WARNING_ACCENT: Record<WarningItem["severity"], string> = {
  high: "#ff8a5b",
  medium: "#d6b25e"
};

function toTitleCase(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function mitigationForBottleneck(detail: string) {
  const lower = detail.toLowerCase();
  if (lower.includes("corridor") || lower.includes("entry") || lower.includes("lane")) {
    return "This choke point will slow patient movement, crowd handoffs, and make it harder for the team to keep treatment areas clear during peak arrival waves. Create a one-way flow lane, pull staging activity away from the pinch point, and post a coordinator there until traffic stabilizes.";
  }
  if (lower.includes("sightline") || lower.includes("visibility")) {
    return "Limited visibility here raises the odds of missed updates, duplicated work, and delayed response when patient conditions change. Relocate command or observation staff to a clearer vantage point and add a runner or radio checkpoint to close the visibility gap.";
  }
  if (lower.includes("only one") || lower.includes("single-person")) {
    return "This creates a single point of failure, so one delay or interruption can ripple outward and stall nearby care steps. Add backup coverage for this role or room and reroute noncritical work elsewhere so the primary operator can stay focused on high-priority cases.";
  }
  if (lower.includes("far") || lower.includes("reachable")) {
    return "When critical supplies sit too far from the treatment zone, clinicians lose time walking, handoffs become less reliable, and throughput drops under pressure. Restage key supplies closer to the care area and dedicate a support runner so treatment staff are not pulled off patient care.";
  }
  return "This issue is likely to add friction to movement or coordination, which can quietly compound as more agents converge on the same area. Reduce travel and handoff friction around this zone, then assign one owner to monitor it until throughput recovers.";
}

function mitigationForResource(detail: string) {
  const lower = detail.toLowerCase();
  if (lower.includes("additional")) {
    return "The current staffing or equipment level will likely be outpaced if arrivals spike, especially in the highest-acuity area. Pull overflow support into that zone first, then rebalance lower-priority coverage once the critical lane is stable.";
  }
  if (lower.includes("iv") || lower.includes("fluids") || lower.includes("blood")) {
    return "A shortage or long retrieval path for this material will directly slow stabilization and can force teams to pause during the most time-sensitive interventions. Stage it at resuscitation rooms immediately and assign a runner to keep replenishment continuous.";
  }
  if (lower.includes("radio") || lower.includes("imaging") || lower.includes("review station")) {
    return "Without this coordination tool, teams will rely on delayed verbal relays and situational awareness will degrade as the floor gets louder and busier. Prioritize the tool where communication is already breaking down so the team can recover faster decision-making.";
  }
  return "If this resource remains under-staged, response times will stretch and staff will waste movement on retrieval instead of treatment. Pre-stage it near peak demand and reserve a fallback cache so care teams are not delayed by retrieval trips.";
}

function buildWarnings(aggregate: ScenarioSwarmAggregate | null): WarningItem[] {
  if (!aggregate) return [];

  const warnings: WarningItem[] = [];

  Object.entries(aggregate.bottleneck_counts)
    .slice(0, 3)
    .forEach(([detail, count]) => {
      warnings.push({
        title: count > 1 ? `Recurring flow blocker (${count} reports)` : "Flow blocker",
        detail,
        mitigation: mitigationForBottleneck(detail),
        severity: count >= 2 ? "high" : "medium"
      });
    });

  Object.entries(aggregate.resource_need_counts)
    .slice(0, 3)
    .forEach(([detail, count]) => {
      warnings.push({
        title: count > 1 ? `Resource gap (${count} requests)` : "Resource gap",
        detail: toTitleCase(detail),
        mitigation: mitigationForResource(detail),
        severity: count >= 2 ? "high" : "medium"
      });
    });

  return warnings.slice(0, 5);
}

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
        aria-label={title}
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

export function SimulationWarnings({ aggregate }: { aggregate: ScenarioSwarmAggregate | null }) {
  const warnings = buildWarnings(aggregate);

  if (warnings.length === 0) return null;

  return (
    <div className="panel" style={{ display: "grid", gap: 14 }}>
      <div>
        <div className="eyebrow">Operational warnings</div>
        <h2 style={{ margin: "8px 0 6px" }}>Warnings</h2>
        <p style={{ margin: 0, fontSize: 14 }}>
          Potential hazards and flow inhibitors surfaced by the swarm, with the fastest intervention to protect throughput.
        </p>
      </div>

      <div style={{ display: "grid", gap: 12 }}>
        {warnings.map((warning, index) => (
          <div
            key={`${warning.title}-${warning.detail}-${index}`}
            className="feed-card"
            style={{
              display: "grid",
              gap: 8,
              borderLeft: `4px solid ${WARNING_ACCENT[warning.severity]}`
            }}
          >
            <div>
              <div className="eyebrow">{warning.severity === "high" ? "High priority" : "Watch closely"}</div>
              <div style={{ fontSize: 16 }}>{warning.title}</div>
            </div>
            <div style={{ fontSize: 14, color: "#111111" }}>{warning.detail}</div>
            <div style={{ fontSize: 13, color: "#111111" }}>
              <span style={{ color: "#555555" }}>Max-efficiency response: </span>
              {warning.mitigation}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
