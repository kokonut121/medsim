"use client";

import { type CSSProperties, useEffect, useRef, useState } from "react";
import * as THREE from "three";

import { useGaussianSplatViewer } from "@/hooks/useGaussianSplatViewer";
import { buildApiUrl, WS_BASE } from "@/lib/runtime";
import { getFallbackSplatUrl, resolveSplatAssetUrl } from "@/lib/splat";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Severity = "CRITICAL" | "HIGH" | "ADVISORY";

interface AnnotationDef {
  id: string;
  severity: Severity;
  domain: string;
  domainLabel: string;
  room: string;
  title: string;
  recommendation: string;
  worldPos: [number, number, number];
  cardSide: "left" | "right";
}

interface ScreenPos {
  x: number;
  y: number;
  visible: boolean;
}

// ---------------------------------------------------------------------------
// Nav graph + pathfinding
// ---------------------------------------------------------------------------

interface NavNode {
  roomId: string;
  type: string;
  zoneTags: string[];
  center: { x: number; y: number; z: number };
}

interface NavEdge {
  from: string;
  to: string;
  distance: number;
}

interface NavGraph {
  nodes: Record<string, NavNode>;
  adj: Record<string, Array<{ to: string; dist: number }>>;
}

function buildNavGraph(rooms: Array<Record<string, unknown>>, edges: Array<Record<string, unknown>>): NavGraph {
  const nodes: Record<string, NavNode> = {};
  for (const r of rooms) {
    const id = r.room_id as string;
    nodes[id] = {
      roomId: id,
      type: (r.type as string) || "",
      zoneTags: (r.zone_tags as string[]) || [],
      center: (r.center as { x: number; y: number; z: number }) || { x: 0, y: 1, z: 0 },
    };
  }

  const adj: Record<string, Array<{ to: string; dist: number }>> = {};
  for (const id of Object.keys(nodes)) adj[id] = [];

  for (const e of edges) {
    const from = e.from as string;
    const to = e.to as string;
    const dist = (e.distance_m as number) || 1;
    if (adj[from]) adj[from].push({ to, dist });
    if (adj[to]) adj[to].push({ to: from, dist });
  }

  return { nodes, adj };
}

/** BFS shortest-hop path between two room IDs. Returns list of room IDs including start+end. */
function bfsPath(graph: NavGraph, start: string, goal: string): string[] {
  if (start === goal) return [start];
  const visited = new Set<string>([start]);
  const queue: Array<{ id: string; path: string[] }> = [{ id: start, path: [start] }];
  while (queue.length) {
    const { id, path } = queue.shift()!;
    for (const { to } of graph.adj[id] || []) {
      if (visited.has(to)) continue;
      visited.add(to);
      const newPath = [...path, to];
      if (to === goal) return newPath;
      queue.push({ id: to, path: newPath });
    }
  }
  return [start]; // unreachable — stay put
}

// ---------------------------------------------------------------------------
// Agent roles + autonomous target selection
// ---------------------------------------------------------------------------

type AgentRole = "nurse" | "instructor" | "emergency_responder" | "supply_staff";

interface AgentSpec {
  id: string;
  role: AgentRole;
  color: string;
  speed: number; // world-units per second
}

const AGENT_SPECS: AgentSpec[] = [
  { id: "nurse-1",       role: "nurse",               color: "#27ae60", speed: 0.55 },
  { id: "nurse-2",       role: "nurse",               color: "#27ae60", speed: 0.48 },
  { id: "instructor-1",  role: "instructor",           color: "#2980b9", speed: 0.60 },
  { id: "responder-1",   role: "emergency_responder",  color: "#c0392b", speed: 1.10 },
  { id: "supply-1",      role: "supply_staff",         color: "#8e44ad", speed: 0.38 },
];

/** Pick the next target room for an agent based on its role and the current findings. */
function pickNextTarget(
  spec: AgentSpec,
  currentRoom: string,
  graph: NavGraph,
  criticalRoomIds: Set<string>,
): string {
  const ids = Object.keys(graph.nodes);
  if (ids.length === 0) return currentRoom;

  const byTag = (tag: string) => ids.filter((id) => graph.nodes[id].zoneTags.includes(tag));
  const byType = (...types: string[]) => ids.filter((id) => types.includes(graph.nodes[id].type));

  switch (spec.role) {
    case "emergency_responder": {
      // Prioritise any CRITICAL finding room; fall back to patient-care rooms
      const targets = criticalRoomIds.size > 0 ? [...criticalRoomIds] : byTag("patient_care");
      const reachable = targets.filter((id) => id !== currentRoom && graph.nodes[id]);
      if (reachable.length) return reachable[Math.floor(Math.random() * reachable.length)];
      break;
    }
    case "nurse": {
      // Rotate through patient-care, then nursing hub, then back
      const pool = [...byTag("patient_care"), ...byTag("nursing_hub")].filter((id) => id !== currentRoom);
      if (pool.length) return pool[Math.floor(Math.random() * pool.length)];
      break;
    }
    case "instructor": {
      // Visits consultation rooms and patient-care rooms
      const pool = [...byTag("consultation"), ...byTag("patient_care")].filter((id) => id !== currentRoom);
      if (pool.length) return pool[Math.floor(Math.random() * pool.length)];
      break;
    }
    case "supply_staff": {
      // Cycles between utility and patient-care
      const pool = [...byTag("utility"), ...byTag("patient_care")].filter((id) => id !== currentRoom);
      if (pool.length) return pool[Math.floor(Math.random() * pool.length)];
      break;
    }
  }

  // Fallback: any room that isn't current
  const fallback = ids.filter((id) => id !== currentRoom);
  return fallback.length ? fallback[Math.floor(Math.random() * fallback.length)] : currentRoom;
}

// ---------------------------------------------------------------------------
// Live agent state — Catmull-Rom spline + eye-height float
// ---------------------------------------------------------------------------

const AGENT_EYE_HEIGHT = 1.65; // metres — shoulder/head height, well above floor
const BOB_AMP = 0.06;          // gentle vertical float amplitude
const JITTER = 0.18;           // lateral randomness added to each waypoint

/** Add small random xz jitter so paths don't snap to exact room-center grid lines. */
function jittered(center: { x: number; y: number; z: number }): THREE.Vector3 {
  return new THREE.Vector3(
    center.x + (Math.random() - 0.5) * 2 * JITTER,
    AGENT_EYE_HEIGHT,
    center.z + (Math.random() - 0.5) * 2 * JITTER,
  );
}

/** Build a Catmull-Rom curve through a list of room IDs in the graph. */
function buildCurve(roomIds: string[], graph: NavGraph): THREE.CatmullRomCurve3 {
  const pts = roomIds.map((id) => jittered(graph.nodes[id]?.center ?? { x: 0, y: 1, z: 0 }));
  // Need at least 2 pts; duplicate endpoints so the curve passes through them
  if (pts.length === 1) pts.push(pts[0].clone());
  return new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.5);
}

interface LiveAgent {
  spec: AgentSpec;
  curve: THREE.CatmullRomCurve3;
  /** 0→1 progress along the current curve */
  t: number;
  /** Approx arc-length of the curve in world units */
  arcLength: number;
  /** World position (updated each tick) */
  pos: THREE.Vector3;
  /** Phase offset for the bob sine wave (unique per agent) */
  bobPhase: number;
  /** Elapsed seconds (for bob) */
  elapsed: number;
  /** Room ID at destination end of current curve */
  destRoom: string;
}

function makeAgents(graph: NavGraph): LiveAgent[] {
  const ids = Object.keys(graph.nodes);
  if (ids.length === 0) return [];

  return AGENT_SPECS.map((spec, i) => {
    const startId = ids[i % ids.length];
    // Pick a random initial destination so agents start spread out
    const destId = ids[(i + Math.floor(ids.length / 2)) % ids.length];
    const path = bfsPath(graph, startId, destId);
    const curve = buildCurve(path, graph);
    const arcLength = curve.getLength() || 1;
    const node = graph.nodes[startId];

    return {
      spec,
      curve,
      t: 0,
      arcLength,
      pos: new THREE.Vector3(node.center.x, AGENT_EYE_HEIGHT, node.center.z),
      bobPhase: i * ((Math.PI * 2) / AGENT_SPECS.length), // spread bob phases
      elapsed: 0,
      destRoom: destId,
    };
  });
}

function tickAgent(
  agent: LiveAgent,
  dt: number,
  graph: NavGraph,
  criticalRoomIds: Set<string>,
): void {
  agent.elapsed += dt;

  // Advance t proportional to speed / arc-length
  const advance = (agent.spec.speed * dt) / agent.arcLength;
  agent.t += advance;

  if (agent.t >= 1) {
    // Arrived — pick a new destination and rebuild curve
    const newDest = pickNextTarget(agent.spec, agent.destRoom, graph, criticalRoomIds);
    const path = bfsPath(graph, agent.destRoom, newDest);
    agent.curve = buildCurve(path, graph);
    agent.arcLength = agent.curve.getLength() || 1;
    agent.t = 0;
    agent.destRoom = newDest;
  }

  // Sample spline position
  const pt = agent.curve.getPoint(Math.min(agent.t, 1));
  // Add sinusoidal bob in Y so agents visibly float, not glued to floor
  const bob = BOB_AMP * Math.sin(agent.elapsed * 1.8 + agent.bobPhase);
  agent.pos.set(pt.x, pt.y + bob, pt.z);
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TARGET_OVERLAY_FPS = 30;
const LIVE_FINDINGS_LIMIT = 5;
const UNIT_ID = "unit_1";

const SEV_COLOR: Record<Severity, string> = {
  CRITICAL: "#e74c3c",
  HIGH: "#e67e22",
  ADVISORY: "#0d7e78",
};

const SEV_GLOW: Record<Severity, string> = {
  CRITICAL: "rgba(231,76,60,0.5)",
  HIGH: "rgba(230,126,34,0.5)",
  ADVISORY: "rgba(13,126,120,0.5)",
};

const DOMAIN_COLOR: Record<string, string> = {
  ICA: "#e74c3c",
  ERA: "#e74c3c",
  MSA: "#e67e22",
  FRA: "#e67e22",
  PFA: "#0d7e78",
  SCA: "#5b2c8d",
};

const DOMAIN_LABEL: Record<string, string> = {
  ICA: "Infection Control",
  ERA: "Emergency Response",
  MSA: "Medication Safety",
  FRA: "Fall Risk",
  PFA: "Patient Flow",
  SCA: "Safe Communication",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function projectToScreen(
  vector: THREE.Vector3,
  camera: THREE.PerspectiveCamera,
  width: number,
  height: number,
): ScreenPos {
  const projected = vector.project(camera);
  const x = ((projected.x + 1) / 2) * width;
  const y = (-(projected.y - 1) / 2) * height;
  return {
    x,
    y,
    visible:
      projected.z >= -1 && projected.z <= 1 &&
      x >= -120 && x <= width + 120 &&
      y >= -120 && y <= height + 120,
  };
}

function updateProjectedElement(el: HTMLElement | null, pos: ScreenPos, pe: "auto" | "none") {
  if (!el) return;
  if (!pos.visible) {
    el.style.opacity = "0";
    el.style.visibility = "hidden";
    el.style.pointerEvents = "none";
    return;
  }
  el.style.opacity = "1";
  el.style.visibility = "visible";
  el.style.pointerEvents = pe;
  el.style.transform = `translate3d(${pos.x}px,${pos.y}px,0) translate(-50%,-50%)`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface WorldViewerProps {
  initialSplatUrl?: string;
}

export function WorldViewer({ initialSplatUrl }: WorldViewerProps) {
  const shellRef = useRef<HTMLDivElement>(null);
  const splatRef = useRef<HTMLDivElement>(null);
  const annotationRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const agentRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const shellSizeRef = useRef({ width: 0, height: 0 });
  const frameRef = useRef<number>(0);
  const lastTickRef = useRef<number>(0);

  // Nav graph + live agents live in refs so RAF doesn't need state updates
  const graphRef = useRef<NavGraph>({ nodes: {}, adj: {} });
  const agentsRef = useRef<LiveAgent[]>([]);
  const criticalRoomsRef = useRef<Set<string>>(new Set());

  const [splatUrl, setSplatUrl] = useState(initialSplatUrl ?? "");
  const [openId, setOpenId] = useState<string | null>(null);
  const [liveFindings, setLiveFindings] = useState<Array<{ id: string; text: string; sev: Severity }>>([]);
  const [annotations, setAnnotations] = useState<AnnotationDef[]>([]);
  // agentIds only used for rendering the DOM elements; positions updated imperatively
  const [agentIds, setAgentIds] = useState<Array<{ id: string; color: string; role: string }>>([]);

  const isIframeUrl = splatUrl.startsWith("https://marble.worldlabs.ai");
  const { viewerRef, loading: gaussianLoading, error } = useGaussianSplatViewer(
    isIframeUrl ? "" : splatUrl,
    splatRef,
  );
  const loading = !splatUrl || (!isIframeUrl && gaussianLoading);

  // Load splat URL
  useEffect(() => {
    if (splatUrl) return;
    let cancelled = false;
    const fallback = getFallbackSplatUrl(UNIT_ID);
    fetch(buildApiUrl(`/api/models/${UNIT_ID}/splat`), { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => { if (!cancelled) setSplatUrl(p ? resolveSplatAssetUrl(p as { signed_url: string; stream_url?: string }) : fallback); })
      .catch(() => { if (!cancelled) setSplatUrl(fallback); });
    return () => { cancelled = true; };
  }, [splatUrl]);

  // Load scene graph → build nav graph → spawn agents
  useEffect(() => {
    let cancelled = false;
    fetch(buildApiUrl(`/api/models/${UNIT_ID}/spatial_bundle`), { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((sg: Record<string, unknown> | null) => {
        if (cancelled || !sg) return;
        const bundleRooms = (sg.rooms as Array<Record<string, unknown>>) ?? [];
        const bundleEdges = (sg.nav_edges as Array<Record<string, unknown>>) ?? [];
        const graph = buildNavGraph(bundleRooms, bundleEdges);
        graphRef.current = graph;
        agentsRef.current = makeAgents(graph);
        setAgentIds(AGENT_SPECS.map((s) => ({ id: s.id, color: s.color, role: s.role })));
      })
      .catch(() => null);
    return () => { cancelled = true; };
  }, []);

  // Load findings → annotations + critical room set for responder targeting
  useEffect(() => {
    let cancelled = false;

    const load = () =>
      fetch(buildApiUrl(`/api/scans/${UNIT_ID}/findings`), { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : []))
        .then((findings: Array<Record<string, unknown>>) => {
          if (cancelled) return;
          if (!findings.length) {
            fetch(buildApiUrl(`/api/scans/${UNIT_ID}/run`), { method: "POST" }).catch(() => null);
            setTimeout(load, 4000);
            return;
          }
          criticalRoomsRef.current = new Set(
            findings
              .filter((f) => f.severity === "CRITICAL")
              .map((f) => f.room_id as string)
              .filter(Boolean),
          );
          const defs: AnnotationDef[] = findings.map((f, i) => {
            const anchor = f.spatial_anchor as { x?: number; y?: number; z?: number } | undefined;
            const sev = (f.severity as string) === "CRITICAL" ? "CRITICAL"
              : (f.severity as string) === "HIGH" ? "HIGH" : "ADVISORY";
            const domain = (f.domain as string) ?? "ICA";
            return {
              id: (f.finding_id as string) ?? `f-${i}`,
              severity: sev as Severity,
              domain,
              domainLabel: DOMAIN_LABEL[domain] ?? domain,
              room: (f.room_id as string) ?? "",
              title: (f.label_text as string) ?? "",
              recommendation: (f.recommendation as string) ?? "",
              worldPos: [anchor?.x ?? 0, anchor?.y ?? 1.0, anchor?.z ?? 0],
              cardSide: i % 2 === 0 ? "right" : "left",
            };
          });
          setAnnotations(defs);
        })
        .catch(() => null);

    load();
    return () => { cancelled = true; };
  }, []);

  // Shell resize
  useEffect(() => {
    const shell = shellRef.current;
    if (!shell) return;
    const update = () => { shellSizeRef.current = { width: shell.clientWidth, height: shell.clientHeight }; };
    update();
    const obs = new ResizeObserver(update);
    obs.observe(shell);
    return () => obs.disconnect();
  }, []);

  // RAF loop — ticks agents and projects all overlays
  useEffect(() => {
    if (isIframeUrl || loading || error) return;

    lastTickRef.current = performance.now();
    const annVec = new THREE.Vector3();
    const agentVec = new THREE.Vector3();
    let lastPaint = 0;

    const tick = (now: number) => {
      frameRef.current = requestAnimationFrame(tick);

      const dt = Math.min((now - lastTickRef.current) / 1000, 0.1); // cap at 100ms
      lastTickRef.current = now;

      // Tick every agent
      for (const agent of agentsRef.current) {
        tickAgent(agent, dt, graphRef.current, criticalRoomsRef.current);
      }

      if (document.hidden || now - lastPaint < 1000 / TARGET_OVERLAY_FPS) return;
      lastPaint = now;

      const viewer = viewerRef.current;
      const { width, height } = shellSizeRef.current;
      if (!viewer?.camera || width === 0 || height === 0) return;

      // Project annotation pins
      for (const ann of annotations) {
        annVec.set(...ann.worldPos);
        updateProjectedElement(
          annotationRefs.current[ann.id],
          projectToScreen(annVec, viewer.camera, width, height),
          "auto",
        );
      }

      // Project agent dots from live positions
      for (const agent of agentsRef.current) {
        agentVec.copy(agent.pos);
        updateProjectedElement(
          agentRefs.current[agent.spec.id],
          projectToScreen(agentVec, viewer.camera, width, height),
          "none",
        );
      }
    };

    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [agentIds, annotations, error, isIframeUrl, loading, viewerRef]);

  // WebSocket live feed
  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/scans/${UNIT_ID}/live`);
    ws.onmessage = (event) => {
      try {
        const finding = JSON.parse(event.data as string) as { finding_id: string; label_text: string; severity: Severity };
        setLiveFindings((cur) => [
          { id: finding.finding_id, text: finding.label_text, sev: finding.severity },
          ...cur.filter((f) => f.id !== finding.finding_id),
        ].slice(0, LIVE_FINDINGS_LIMIT));
      } catch { /* ignore */ }
    };
    return () => ws.close();
  }, []);

  const annotationCounts = annotations.reduce(
    (acc, a) => { acc[a.severity]++; return acc; },
    { CRITICAL: 0, HIGH: 0, ADVISORY: 0 } as Record<Severity, number>,
  );

  return (
    <div ref={shellRef} className="world-shell">
      {isIframeUrl ? (
        <iframe
          src={splatUrl}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", border: "none" }}
          allow="xr-spatial-tracking; accelerometer; gyroscope"
          title="World reconstruction"
        />
      ) : (
        <div ref={splatRef} style={{ position: "absolute", inset: 0 }} />
      )}

      {loading ? (
        <div className="world-loading">
          <div className="world-loading__ring" />
          <p>Loading world model…</p>
        </div>
      ) : null}

      {error && !loading ? (
        <div className="world-loading">
          <p style={{ color: SEV_COLOR.CRITICAL }}>⚠ {error}</p>
        </div>
      ) : null}

      <div className="world-overlay">
        {annotations.map((ann) => {
          const color = SEV_COLOR[ann.severity];
          const glow = SEV_GLOW[ann.severity];
          const domainColor = DOMAIN_COLOR[ann.domain] ?? color;
          const isOpen = openId === ann.id;

          return (
            <div
              key={ann.id}
              ref={(node) => { annotationRefs.current[ann.id] = node; }}
              className="ann-pin"
              style={{ opacity: 0, visibility: "hidden", pointerEvents: "none" }}
              onMouseEnter={() => setOpenId(ann.id)}
              onMouseLeave={() => setOpenId(null)}
              onClick={() => setOpenId((c) => (c === ann.id ? null : ann.id))}
            >
              <span className={`ann-pulse ann-pulse--${ann.severity.toLowerCase()}`} style={{ "--glow": glow } as CSSProperties} />
              <span className={`ann-pulse ann-pulse--${ann.severity.toLowerCase()} ann-pulse--delay`} style={{ "--glow": glow } as CSSProperties} />
              <span className="ann-dot" style={{ background: color, boxShadow: `0 0 0 2px rgba(255,255,255,.3),0 0 12px ${glow}` }} />
              <span className="ann-badge" style={{ background: domainColor }}>{ann.domain}</span>
              {isOpen ? (
                <div className={`ann-card ann-card--${ann.cardSide}`} style={{ "--cc": color } as CSSProperties}>
                  <div className="ann-card__row">
                    <span className="ann-card__sev" style={{ background: color }}>{ann.severity}</span>
                    <span className="ann-card__domain">{ann.domainLabel}</span>
                    <span className="ann-card__room">{ann.room}</span>
                  </div>
                  <p className="ann-card__title">{ann.title}</p>
                  <p className="ann-card__rec">→ {ann.recommendation}</p>
                </div>
              ) : null}
            </div>
          );
        })}

        {agentIds.map((a) => (
          <div
            key={a.id}
            ref={(node) => { agentRefs.current[a.id] = node; }}
            className="agent-dot"
            title={a.role}
            style={{ background: a.color, opacity: 0, visibility: "hidden" }}
          />
        ))}
      </div>

      <div className="world-brand">
        <span className="world-brand__logo">MedSentinel</span>
        <span className="world-brand__sub">LeTourneau University · Nursing Skills Lab · Live scan</span>
      </div>

      {liveFindings.length > 0 ? (
        <div className="world-ticker">
          {liveFindings.map((f, i) => (
            <div key={f.id} className={`world-tick world-tick--${f.sev.toLowerCase()}`} style={{ opacity: 1 - i * 0.18 }}>
              <span className="world-tick__sev">{f.sev}</span>
              {f.text.slice(0, 72)}{f.text.length > 72 ? "…" : ""}
            </div>
          ))}
        </div>
      ) : null}

      <div className="world-stats">
        <div className="world-stat world-stat--critical">
          <span className="world-stat__num">{annotationCounts.CRITICAL}</span>
          <span className="world-stat__label">Critical</span>
        </div>
        <div className="world-stat world-stat--high">
          <span className="world-stat__num">{annotationCounts.HIGH}</span>
          <span className="world-stat__label">High</span>
        </div>
        <div className="world-stat world-stat--advisory">
          <span className="world-stat__num">{annotationCounts.ADVISORY}</span>
          <span className="world-stat__label">Advisory</span>
        </div>
        <div className="world-stat world-stat--gain">
          <span className="world-stat__num">+5%</span>
          <span className="world-stat__label">Efficiency gain</span>
        </div>
        <div className="world-stat">
          <span className="world-stat__num">{agentIds.length}</span>
          <span className="world-stat__label">Agents active</span>
        </div>
        <a href="/dashboard" className="world-cta">Open dashboard →</a>
      </div>
    </div>
  );
}
