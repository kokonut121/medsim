"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import cytoscape, {
  type Core,
  type ElementDefinition,
  type EventObject,
  type LayoutOptions,
  type StylesheetCSS
} from "cytoscape";
// @ts-expect-error cytoscape-fcose ships no type declarations
import fcose from "cytoscape-fcose";

import { useStore } from "@/store";
import type { ScenarioGraphNode, ScenarioGraphSnapshot } from "@/types";

let fcoseRegistered = false;
function ensureFcose() {
  if (fcoseRegistered) return;
  // cytoscape-fcose mutates the cytoscape singleton; register exactly once.
  cytoscape.use(fcose);
  fcoseRegistered = true;
}

const AGENT_NAME: Record<string, string> = {
  incident_commander: "commander",
  triage_officer: "triage",
  burn_specialist: "burn",
  trauma_surgeon: "surgeon",
  anesthesiologist: "anesthesia",
  resource_allocator: "allocator",
  scenario_patient: "patient",
  nurse: "nurse",
  doctor: "doctor"
};

type Tokens = {
  midnight: string;
  midnightCard: string;
  midnightElev: string;
  bone: string;
  boneSoft: string;
  boneChalk: string;
  boneChalkHi: string;
  signal: string;
  ember: string;
  phosphor: string;
  amber: string;
  royal: string;
};

const FALLBACK_TOKENS: Tokens = {
  midnight: "#060a09",
  midnightCard: "#111918",
  midnightElev: "#0c1211",
  bone: "#f0eadc",
  boneSoft: "rgba(240, 234, 220, 0.60)",
  boneChalk: "rgba(240, 234, 220, 0.14)",
  boneChalkHi: "rgba(240, 234, 220, 0.30)",
  signal: "#e63a2e",
  ember: "#e8842c",
  phosphor: "#2dc7a0",
  amber: "#d9a441",
  royal: "#3a3a9e"
};

const LEGEND_ITEMS = [
  { label: "Agent", tone: "midnight" as const, shape: "circle" as const },
  { label: "Task", tone: "amber" as const, shape: "square" as const },
  { label: "Critical task", tone: "ember" as const, shape: "square" as const },
  { label: "Challenge", tone: "signal" as const, shape: "diamond" as const },
  { label: "Supervisor insight", tone: "phosphor" as const, shape: "hex" as const }
];

function readCssTokens(): Tokens {
  if (typeof window === "undefined") return FALLBACK_TOKENS;
  const root = getComputedStyle(document.documentElement);
  const get = (name: string, fallback: string) => {
    const value = root.getPropertyValue(name).trim();
    return value || fallback;
  };
  return {
    midnight: get("--midnight", FALLBACK_TOKENS.midnight),
    midnightCard: get("--midnight-card", FALLBACK_TOKENS.midnightCard),
    midnightElev: get("--midnight-elev", FALLBACK_TOKENS.midnightElev),
    bone: get("--bone", FALLBACK_TOKENS.bone),
    boneSoft: get("--bone-soft", FALLBACK_TOKENS.boneSoft),
    boneChalk: get("--bone-chalk", FALLBACK_TOKENS.boneChalk),
    boneChalkHi: get("--bone-chalk-hi", FALLBACK_TOKENS.boneChalkHi),
    signal: get("--signal", FALLBACK_TOKENS.signal),
    ember: get("--ember", FALLBACK_TOKENS.ember),
    phosphor: get("--phosphor", FALLBACK_TOKENS.phosphor),
    amber: get("--amber", FALLBACK_TOKENS.amber),
    royal: get("--royal", FALLBACK_TOKENS.royal)
  };
}

function shortRoom(roomId: string | null) {
  return roomId ? roomId.replace(/^NL-/, "") : "unplaced";
}

function nodeLabel(node: ScenarioGraphNode): string {
  if (node.kind === "agent") {
    const role = AGENT_NAME[node.role_kind ?? ""] ?? node.label;
    return `${role.toLowerCase()}\n${node.label}`;
  }
  if (node.kind === "role") {
    return (AGENT_NAME[node.role_kind ?? ""] ?? node.label).toLowerCase();
  }
  if (node.kind === "task" || node.kind === "challenge" || node.kind === "insight") {
    return node.label.length > 28 ? `${node.label.slice(0, 26)}…` : node.label;
  }
  return node.label;
}

function elementsFromSnapshot(
  snapshot: ScenarioGraphSnapshot
): { elements: ElementDefinition[]; highlightedIds: Set<string> } {
  const elements: ElementDefinition[] = [];
  const nodeIds = new Set(snapshot.nodes.map((n) => n.id));

  for (const node of snapshot.nodes) {
    elements.push({
      group: "nodes",
      data: {
        id: node.id,
        label: nodeLabel(node),
        kind: node.kind,
        role_kind: node.role_kind ?? "",
        emphasis: node.emphasis ?? "",
        room_id: node.room_id ?? "",
        detail: node.detail ?? "",
        raw: node
      }
    });
  }

  for (const edge of snapshot.edges) {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) continue;
    elements.push({
      group: "edges",
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label ?? "",
        kind: edge.kind,
        urgency: edge.urgency ?? "",
        raw: edge
      }
    });
  }

  return { elements, highlightedIds: new Set(snapshot.highlighted_node_ids ?? []) };
}

function buildStylesheet(tokens: Tokens): StylesheetCSS[] {
  return [
    {
      selector: "node",
      css: {
        "background-color": tokens.midnightCard,
        "border-color": tokens.boneChalkHi,
        "border-width": 1,
        color: tokens.bone,
        label: "data(label)",
        "font-family": "'IBM Plex Sans', sans-serif",
        "font-size": 10,
        "font-weight": 600,
        "text-valign": "center",
        "text-halign": "center",
        "text-wrap": "wrap",
        "text-max-width": "82px",
        "text-outline-color": tokens.midnight,
        "text-outline-width": 2,
        width: 34,
        height: 34
      }
    },
    {
      selector: 'node[kind = "agent"]',
      css: {
        "background-color": tokens.midnightCard,
        "border-color": tokens.bone,
        "border-width": 1.5,
        width: 64,
        height: 64,
        "font-size": 11,
        "text-transform": "uppercase",
        "line-height": 1.15,
        "text-max-width": "58px"
      }
    },
    {
      selector: 'node[kind = "agent"][emphasis = "high"]',
      css: {
        "border-color": tokens.signal,
        "border-width": 2.5
      }
    },
    {
      selector: 'node[kind = "role"]',
      css: {
        "background-color": tokens.midnightElev,
        "border-color": tokens.boneChalkHi,
        "border-style": "dashed",
        width: 48,
        height: 48,
        "font-size": 10
      }
    },
    {
      selector: 'node[kind = "task"]',
      css: {
        "background-color": tokens.amber,
        "border-color": tokens.amber,
        color: tokens.midnight,
        "text-outline-color": tokens.amber,
        "text-outline-width": 0,
        width: 58,
        height: 58,
        shape: "round-rectangle",
        "font-size": 9.5,
        "text-max-width": "54px",
        padding: "8px"
      }
    },
    {
      selector: 'node[kind = "task"][emphasis = "critical"]',
      css: {
        "background-color": tokens.ember,
        "border-color": tokens.ember,
        "text-outline-color": tokens.ember
      }
    },
    {
      selector: 'node[kind = "challenge"]',
      css: {
        "background-color": tokens.signal,
        "border-color": tokens.signal,
        color: tokens.bone,
        "text-outline-color": tokens.signal,
        width: 46,
        height: 46,
        shape: "diamond",
        "font-size": 9,
        "text-max-width": "44px"
      }
    },
    {
      selector: 'node[kind = "challenge"][emphasis = "high"]',
      css: {
        "background-color": tokens.ember,
        "border-color": tokens.ember,
        "text-outline-color": tokens.ember
      }
    },
    {
      selector: 'node[kind = "insight"]',
      css: {
        "background-color": tokens.phosphor,
        "border-color": tokens.phosphor,
        color: tokens.midnight,
        "text-outline-color": tokens.phosphor,
        "text-outline-width": 0,
        width: 56,
        height: 56,
        shape: "hexagon",
        "font-size": 10
      }
    },
    {
      selector: "node.highlight",
      css: {
        "border-color": tokens.bone,
        "border-width": 3
      }
    },
    {
      selector: "node:selected",
      css: {
        "border-color": tokens.bone,
        "border-width": 3,
        "overlay-color": tokens.bone,
        "overlay-opacity": 0.06,
        "overlay-padding": 6
      }
    },
    {
      selector: "edge",
      css: {
        width: 1.4,
        "line-color": tokens.boneChalkHi,
        "target-arrow-color": tokens.boneChalkHi,
        "target-arrow-shape": "triangle",
        "arrow-scale": 0.9,
        "curve-style": "bezier",
        opacity: 0.85
      }
    },
    {
      selector: 'edge[kind = "owns"]',
      css: {
        "line-color": tokens.amber,
        "target-arrow-color": tokens.amber,
        width: 1.6
      }
    },
    {
      selector: 'edge[kind = "blocked_by"]',
      css: {
        "line-color": tokens.signal,
        "target-arrow-color": tokens.signal,
        "line-style": "dashed",
        width: 1.6
      }
    },
    {
      selector: 'edge[kind = "handoff"]',
      css: {
        "line-color": tokens.phosphor,
        "target-arrow-color": tokens.phosphor,
        width: 2.2,
        "curve-style": "bezier",
        "line-style": "dashed"
      }
    },
    {
      selector: 'edge[kind = "supports"]',
      css: {
        "line-color": tokens.phosphor,
        "target-arrow-color": tokens.phosphor,
        "line-style": "dotted",
        width: 1.6
      }
    },
    {
      selector: 'edge[kind = "highlight"]',
      css: {
        "line-color": tokens.bone,
        "target-arrow-color": tokens.bone,
        width: 2,
        "line-style": "dashed"
      }
    }
  ];
}

const FCOSE_LAYOUT: LayoutOptions = {
  name: "fcose",
  // @ts-expect-error fcose layout options are not in the cytoscape type defs
  randomize: false,
  animate: "end",
  animationDuration: 600,
  fit: false,
  nodeRepulsion: 8000,
  idealEdgeLength: 110,
  edgeElasticity: 0.25,
  gravity: 0.18,
  padding: 30,
  packComponents: true,
  nodeSeparation: 90,
  numIter: 1500
};

function GraphInner() {
  const graph = useStore((state) => state.reasoningGraph);
  const status = useStore((state) => state.simulationStatus);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const tokens = useMemo(() => readCssTokens(), []);

  const snapshot = graph;

  // Mount Cytoscape exactly once.
  useEffect(() => {
    if (!containerRef.current) return;
    ensureFcose();
    const cy = cytoscape({
      container: containerRef.current,
      elements: [],
      style: buildStylesheet(tokens),
      wheelSensitivity: 0.25,
      minZoom: 0.3,
      maxZoom: 2.4,
      boxSelectionEnabled: false
    });
    cyRef.current = cy;

    const handleTap = (event: EventObject) => {
      const node = event.target;
      setSelectedId(node.id());
    };
    const handleBgTap = (event: EventObject) => {
      if (event.target === cy) {
        setSelectedId(null);
      }
    };
    cy.on("tap", "node", handleTap);
    cy.on("tap", handleBgTap);

    return () => {
      cy.off("tap", "node", handleTap);
      cy.off("tap", handleBgTap);
      cy.destroy();
      cyRef.current = null;
    };
  }, []);

  // Diff the snapshot into Cytoscape and re-run the incremental layout.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    if (!snapshot || snapshot.nodes.length === 0) {
      cy.elements().remove();
      return;
    }
    const { elements, highlightedIds } = elementsFromSnapshot(snapshot);
    const incomingIds = new Set(elements.map((el) => String(el.data.id)));

    cy.batch(() => {
      // Remove anything not in the new snapshot.
      cy.elements().forEach((el) => {
        if (!incomingIds.has(el.id())) {
          el.remove();
        }
      });

      // Upsert nodes and edges. Existing elements get their data refreshed
      // (label / emphasis may have changed) without losing their positions.
      for (const element of elements) {
        const id = String(element.data.id);
        const existing = cy.getElementById(id);
        if (existing && existing.length > 0) {
          existing.data(element.data);
        } else {
          cy.add(element);
        }
      }

      // Re-apply highlight class.
      cy.nodes().removeClass("highlight");
      highlightedIds.forEach((id) => {
        const node = cy.getElementById(id);
        if (node && node.length > 0) node.addClass("highlight");
      });
    });

    const layout = cy.layout(FCOSE_LAYOUT);
    layout.run();
  }, [snapshot]);

  const selected = useMemo<ScenarioGraphNode | null>(() => {
    const nodes = snapshot?.nodes ?? [];
    if (selectedId) {
      const match = nodes.find((node) => node.id === selectedId);
      if (match) return match;
    }
    return nodes.find((node) => node.kind === "agent") ?? null;
  }, [snapshot, selectedId]);

  const summary = useMemo(() => {
    const nodes = snapshot?.nodes ?? [];
    return {
      agents: nodes.filter((node) => node.kind === "agent").length,
      tasks: nodes.filter((node) => node.kind === "task").length,
      challenges: nodes.filter((node) => node.kind === "challenge").length,
      insights: nodes.filter((node) => node.kind === "insight").length
    };
  }, [snapshot]);

  const legendTone = (tone: (typeof LEGEND_ITEMS)[number]["tone"]) => {
    switch (tone) {
      case "amber":
        return tokens.amber;
      case "ember":
        return tokens.ember;
      case "signal":
        return tokens.signal;
      case "phosphor":
        return tokens.phosphor;
      default:
        return tokens.midnightCard;
    }
  };

  const legendShapeStyle = (shape: (typeof LEGEND_ITEMS)[number]["shape"]) => {
    if (shape === "diamond") return { borderRadius: 4, transform: "rotate(45deg)" };
    if (shape === "hex") return { clipPath: "polygon(25% 6%, 75% 6%, 100% 50%, 75% 94%, 25% 94%, 0% 50%)" };
    if (shape === "circle") return { borderRadius: "999px" };
    return { borderRadius: 6 };
  };

  return (
    <div className="panel" style={{ display: "grid", gap: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline" }}>
        <div>
          <div className="eyebrow">Reasoning graph</div>
          <h2 style={{ margin: "8px 0 4px" }}>Live coordination map</h2>
          <div className="muted" style={{ fontSize: 13, maxWidth: 580 }}>
            Agent handoffs, active work packets, blockers, and supervisor overlays in one live coordination surface.
          </div>
        </div>
        <div
          style={{
            display: "grid",
            gap: 10,
            minWidth: 180,
            padding: "12px 14px",
            borderRadius: 14,
            background: "rgba(240,234,220,0.42)",
            border: "1px solid rgba(11,16,15,0.10)",
            boxShadow: "0 16px 40px rgba(11,16,15,0.08)"
          }}
        >
          <div className="muted" style={{ fontSize: 12, textAlign: "right" }}>
            phase
            <br />
            <strong style={{ fontSize: 16, textTransform: "capitalize", color: "var(--ink)" }}>
              {snapshot?.phase ?? status ?? "idle"}
            </strong>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
              gap: 8
            }}
          >
            {[
              { label: "Agents", value: summary.agents },
              { label: "Tasks", value: summary.tasks },
              { label: "Risks", value: summary.challenges },
              { label: "Insights", value: summary.insights }
            ].map((item) => (
              <div
                key={item.label}
                style={{
                  padding: "8px 10px",
                  borderRadius: 10,
                  background: "rgba(250,244,228,0.66)",
                  border: "1px solid rgba(11,16,15,0.08)"
                }}
              >
                <div className="muted" style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.12em" }}>
                  {item.label}
                </div>
                <strong style={{ display: "block", marginTop: 2, fontSize: 16 }}>{item.value}</strong>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div
        style={{
          position: "relative",
          height: 760,
          borderRadius: 22,
          overflow: "hidden",
          border: "1px solid rgba(240,234,220,0.12)",
          boxShadow: "0 28px 80px rgba(11,16,15,0.16)",
          background:
            "radial-gradient(ellipse 90% 60% at 50% 0%, rgba(45,199,160,0.08), transparent 60%), radial-gradient(circle at 0% 0%, rgba(230,58,46,0.06), transparent 28%), linear-gradient(180deg, rgba(7,14,13,0.98), rgba(3,7,6,1))"
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            backgroundImage:
              "linear-gradient(rgba(240,234,220,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(240,234,220,0.035) 1px, transparent 1px)",
            backgroundSize: "36px 36px",
            maskImage: "linear-gradient(180deg, rgba(0,0,0,0.62), rgba(0,0,0,1) 18%, rgba(0,0,0,1))"
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 16,
            left: 16,
            zIndex: 1,
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
            pointerEvents: "none"
          }}
        >
          {[
            { label: "Handoffs", color: tokens.phosphor },
            { label: "Task ownership", color: tokens.amber },
            { label: "Blockers", color: tokens.signal }
          ].map((item) => (
            <div
              key={item.label}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "7px 10px",
                borderRadius: 999,
                background: "rgba(6,10,9,0.72)",
                border: "1px solid rgba(240,234,220,0.10)",
                color: "rgba(240,234,220,0.88)",
                fontSize: 11,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                backdropFilter: "blur(10px)"
              }}
            >
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 999,
                  background: item.color,
                  boxShadow: `0 0 12px ${item.color}`
                }}
              />
              {item.label}
            </div>
          ))}
        </div>
        <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />
        {(!snapshot || snapshot.nodes.length === 0) && (
          <div
            className="muted"
            style={{
              position: "absolute",
              inset: 0,
              display: "grid",
              placeItems: "center",
              fontSize: 13
            }}
          >
            Launch a scenario to see the graph assemble live.
          </div>
        )}
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 10,
          padding: "14px 16px",
          borderRadius: 14,
          background: "rgba(250,244,228,0.56)",
          border: "1px solid rgba(11,16,15,0.08)"
        }}
      >
        {LEGEND_ITEMS.map((item) => (
          <div
            key={item.label}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "6px 10px",
              borderRadius: 999,
              background: "rgba(255,255,255,0.28)",
              border: "1px solid rgba(11,16,15,0.06)"
            }}
          >
            <span
              style={{
                display: "inline-block",
                width: 14,
                height: 14,
                background: legendTone(item.tone),
                border: item.tone === "midnight" ? `1.5px solid ${tokens.bone}` : "none",
                ...legendShapeStyle(item.shape)
              }}
            />
            <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>{item.label}</span>
          </div>
        ))}
      </div>

      {selected && (
        <div
          style={{
            display: "grid",
            gap: 8,
            padding: 16,
            borderRadius: 16,
            background: "linear-gradient(180deg, rgba(250,244,228,0.62), rgba(240,234,220,0.40))",
            border: "1px solid rgba(11,16,15,0.10)",
            boxShadow: "0 16px 36px rgba(11,16,15,0.06)"
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline" }}>
            <div>
              <div className="eyebrow">{selected.kind.replaceAll("_", " ")}</div>
              <strong>{selected.label}</strong>
            </div>
            {selected.room_id && (
              <div className="muted" style={{ fontSize: 12 }}>
                {shortRoom(selected.room_id)}
              </div>
            )}
          </div>
          <div className="muted" style={{ fontSize: 13, lineHeight: 1.55 }}>
            {selected.detail || "No expanded detail yet."}
          </div>
        </div>
      )}
    </div>
  );
}

export function AgentReasoningGraph() {
  return <GraphInner />;
}
