"use client";

import { type CSSProperties, useEffect, useRef, useState } from "react";
import * as THREE from "three";

import { useGaussianSplatViewer } from "@/hooks/useGaussianSplatViewer";
import { buildApiUrl, WS_BASE } from "@/lib/runtime";
import { getFallbackSplatUrl, resolveSplatAssetUrl } from "@/lib/splat";

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

interface AgentDef {
  id: string;
  role: string;
  color: string;
  path: Array<[number, number, number]>;
  speed: number;
}

interface ScreenPos {
  x: number;
  y: number;
  visible: boolean;
}

interface AgentPathDef extends AgentDef {
  segmentLengths: number[];
  totalLength: number;
}

const TARGET_OVERLAY_FPS = 30;
const LIVE_FINDINGS_LIMIT = 5;
const UNIT_ID = "unit_1";

// Grid → world coordinate mapping (must match backend team_utils.py)
const GRID_SCALE = 0.8;
const COL_ORIGIN = 2.0;
const ROW_ORIGIN = 1.5;

function gridToWorld(col: number, row: number): [number, number, number] {
  return [(col - COL_ORIGIN) * GRID_SCALE, 1.0, (row - ROW_ORIGIN) * GRID_SCALE];
}

const AGENT_ROLES = [
  { role: "nurse", color: "#27ae60", speed: 0.55 },
  { role: "nurse", color: "#27ae60", speed: 0.48 },
  { role: "instructor", color: "#2980b9", speed: 0.65 },
  { role: "emergency_responder", color: "#c0392b", speed: 1.05 },
  { role: "supply_staff", color: "#8e44ad", speed: 0.38 },
];

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

function buildAgentPaths(rooms: Array<Record<string, unknown>>): AgentPathDef[] {
  const corridors = rooms.filter((r) => r.type === "corridor" || r.type === "hallway");
  const patientRooms = rooms.filter((r) =>
    ["patient_room", "icu_bay", "simulation_room", "skills_lab"].includes(r.type as string),
  );

  const corridorWaypoints: Array<[number, number, number]> = corridors
    .sort((a, b) => {
      const aCol = (a.grid_col as number) ?? 0;
      const bCol = (b.grid_col as number) ?? 0;
      return aCol - bCol;
    })
    .map((r) => gridToWorld((r.grid_col as number) ?? 0, (r.grid_row as number) ?? 0));

  if (corridorWaypoints.length < 2) {
    // Fallback: scatter around origin
    corridorWaypoints.push([-1, 1, -1], [1, 1, -1], [1, 1, 1], [-1, 1, 1]);
  }
  const loopPath: Array<[number, number, number]> = [...corridorWaypoints, corridorWaypoints[0]];

  return AGENT_ROLES.map((roleInfo, i) => {
    let path: Array<[number, number, number]>;
    if (i < 2) {
      // Nurses: follow corridor loop
      path = loopPath;
    } else if (i === 2 && patientRooms.length > 0) {
      // Instructor: visits patient/sim rooms
      const roomWaypoints = patientRooms.slice(0, 4).map((r) =>
        gridToWorld((r.grid_col as number) ?? 0, (r.grid_row as number) ?? 0),
      );
      path = [...roomWaypoints, roomWaypoints[0]];
    } else if (i === 3) {
      // Emergency responder: fast patrol of corridor
      path = loopPath;
    } else {
      // Supply: a subset of corridor
      const halfLen = Math.max(2, Math.floor(corridorWaypoints.length / 2));
      path = [...corridorWaypoints.slice(0, halfLen), ...corridorWaypoints.slice(0, halfLen).reverse()];
    }

    const segmentLengths: number[] = [];
    let totalLength = 0;
    for (let j = 0; j < path.length - 1; j++) {
      const len = Math.hypot(
        path[j + 1][0] - path[j][0],
        path[j + 1][1] - path[j][1],
        path[j + 1][2] - path[j][2],
      );
      segmentLengths.push(len);
      totalLength += len;
    }

    return {
      id: `${roleInfo.role}-${i + 1}`,
      role: roleInfo.role,
      color: roleInfo.color,
      speed: roleInfo.speed,
      path,
      segmentLengths,
      totalLength: totalLength || 1,
    };
  });
}

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
      projected.z >= -1 &&
      projected.z <= 1 &&
      x >= -120 &&
      x <= width + 120 &&
      y >= -120 &&
      y <= height + 120,
  };
}

function interpolatePath(
  agent: AgentPathDef,
  distance: number,
  target: THREE.Vector3,
): THREE.Vector3 {
  const normalizedDistance =
    ((distance % agent.totalLength) + agent.totalLength) % agent.totalLength;
  let traversed = 0;

  for (let index = 0; index < agent.segmentLengths.length; index += 1) {
    const segmentLength = agent.segmentLengths[index];

    if (traversed + segmentLength >= normalizedDistance) {
      const start = agent.path[index];
      const end = agent.path[index + 1];
      const progress = segmentLength === 0 ? 0 : (normalizedDistance - traversed) / segmentLength;

      return target.set(
        start[0] + (end[0] - start[0]) * progress,
        start[1] + (end[1] - start[1]) * progress,
        start[2] + (end[2] - start[2]) * progress,
      );
    }

    traversed += segmentLength;
  }

  const [x, y, z] = agent.path[0];
  return target.set(x, y, z);
}

function updateProjectedElement(
  element: HTMLElement | null,
  position: ScreenPos,
  pointerEvents: "auto" | "none",
) {
  if (!element) {
    return;
  }

  if (!position.visible) {
    element.style.opacity = "0";
    element.style.visibility = "hidden";
    element.style.pointerEvents = "none";
    return;
  }

  element.style.opacity = "1";
  element.style.visibility = "visible";
  element.style.pointerEvents = pointerEvents;
  element.style.transform = `translate3d(${position.x}px, ${position.y}px, 0) translate(-50%, -50%)`;
}

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
  const startTimeRef = useRef(0);

  const [splatUrl, setSplatUrl] = useState(initialSplatUrl ?? "");
  const [openId, setOpenId] = useState<string | null>(null);
  const [liveFindings, setLiveFindings] = useState<
    Array<{ id: string; text: string; sev: Severity }>
  >([]);
  const [annotations, setAnnotations] = useState<AnnotationDef[]>([]);
  const [agentPaths, setAgentPaths] = useState<AgentPathDef[]>([]);

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
      .then((payload) => {
        if (cancelled) return;
        setSplatUrl(payload ? resolveSplatAssetUrl(payload as { signed_url: string; stream_url?: string }) : fallback);
      })
      .catch(() => { if (!cancelled) setSplatUrl(fallback); });

    return () => { cancelled = true; };
  }, [splatUrl]);

  // Load findings from API → annotations; trigger scan if empty
  useEffect(() => {
    let cancelled = false;

    const load = () =>
      fetch(buildApiUrl(`/api/scans/${UNIT_ID}/findings`), { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : []))
        .then((findings: Array<Record<string, unknown>>) => {
          if (cancelled) return;
          if (!findings.length) {
            // Trigger a scan and retry after a delay
            fetch(buildApiUrl(`/api/scans/${UNIT_ID}/trigger`), { method: "POST" }).catch(() => null);
            setTimeout(load, 4000);
            return;
          }
          const defs: AnnotationDef[] = findings.map((f, i) => {
            const anchor = f.spatial_anchor as { x?: number; y?: number; z?: number } | undefined;
            const severity = (f.severity as string) === "HIGH" ? "HIGH"
              : (f.severity as string) === "CRITICAL" ? "CRITICAL"
              : "ADVISORY";
            const domain = (f.domain as string) ?? "ICA";
            return {
              id: (f.finding_id as string) ?? `f-${i}`,
              severity: severity as Severity,
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

  // Load scene graph → build agent patrol paths
  useEffect(() => {
    let cancelled = false;

    fetch(buildApiUrl(`/api/models/${UNIT_ID}/scene_graph`), { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((sg: Record<string, unknown> | null) => {
        if (cancelled || !sg) return;
        const rooms = (sg.rooms as Array<Record<string, unknown>>) ?? [];
        setAgentPaths(buildAgentPaths(rooms));
      })
      .catch(() => null);

    return () => { cancelled = true; };
  }, []);

  // Shell resize observer
  useEffect(() => {
    const shell = shellRef.current;
    if (!shell) return;
    const updateSize = () => {
      shellSizeRef.current = { width: shell.clientWidth, height: shell.clientHeight };
    };
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(shell);
    return () => observer.disconnect();
  }, []);

  // RAF loop
  useEffect(() => {
    if (isIframeUrl || loading || error) return;

    startTimeRef.current = performance.now();
    const annotationVector = new THREE.Vector3();
    const agentVector = new THREE.Vector3();
    let lastPaint = 0;

    const tick = (now: number) => {
      frameRef.current = requestAnimationFrame(tick);

      if (document.hidden || now - lastPaint < 1000 / TARGET_OVERLAY_FPS) return;
      lastPaint = now;

      const viewer = viewerRef.current;
      const { width, height } = shellSizeRef.current;
      if (!viewer?.camera || width === 0 || height === 0) return;

      for (const annotation of annotations) {
        annotationVector.set(...annotation.worldPos);
        updateProjectedElement(
          annotationRefs.current[annotation.id],
          projectToScreen(annotationVector, viewer.camera, width, height),
          "auto",
        );
      }

      const elapsedSeconds = (now - startTimeRef.current) / 1000;

      for (const agent of agentPaths) {
        const worldPosition = interpolatePath(agent, elapsedSeconds * agent.speed, agentVector);
        updateProjectedElement(
          agentRefs.current[agent.id],
          projectToScreen(worldPosition, viewer.camera, width, height),
          "none",
        );
      }
    };

    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [agentPaths, annotations, error, isIframeUrl, loading, viewerRef]);

  // WebSocket live feed
  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/scans/${UNIT_ID}/live`);

    ws.onmessage = (event) => {
      try {
        const finding = JSON.parse(event.data as string) as {
          finding_id: string;
          label_text: string;
          severity: Severity;
        };

        setLiveFindings((current) => [
          { id: finding.finding_id, text: finding.label_text, sev: finding.severity },
          ...current.filter((item) => item.id !== finding.finding_id),
        ].slice(0, LIVE_FINDINGS_LIMIT));
      } catch {
        // Ignore malformed development events.
      }
    };

    return () => ws.close();
  }, []);

  const annotationCounts = annotations.reduce(
    (counts, a) => { counts[a.severity] += 1; return counts; },
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
        {annotations.map((annotation) => {
          const color = SEV_COLOR[annotation.severity];
          const glow = SEV_GLOW[annotation.severity];
          const domainColor = DOMAIN_COLOR[annotation.domain] ?? color;
          const isOpen = openId === annotation.id;

          return (
            <div
              key={annotation.id}
              ref={(node) => { annotationRefs.current[annotation.id] = node; }}
              className="ann-pin"
              style={{ opacity: 0, visibility: "hidden", pointerEvents: "none" }}
              onMouseEnter={() => setOpenId(annotation.id)}
              onMouseLeave={() => setOpenId(null)}
              onClick={() => setOpenId((current) => (current === annotation.id ? null : annotation.id))}
            >
              <span
                className={`ann-pulse ann-pulse--${annotation.severity.toLowerCase()}`}
                style={{ "--glow": glow } as CSSProperties}
              />
              <span
                className={`ann-pulse ann-pulse--${annotation.severity.toLowerCase()} ann-pulse--delay`}
                style={{ "--glow": glow } as CSSProperties}
              />

              <span
                className="ann-dot"
                style={{
                  background: color,
                  boxShadow: `0 0 0 2px rgba(255,255,255,.3), 0 0 12px ${glow}`,
                }}
              />

              <span className="ann-badge" style={{ background: domainColor }}>
                {annotation.domain}
              </span>

              {isOpen ? (
                <div
                  className={`ann-card ann-card--${annotation.cardSide}`}
                  style={{ "--cc": color } as CSSProperties}
                >
                  <div className="ann-card__row">
                    <span className="ann-card__sev" style={{ background: color }}>
                      {annotation.severity}
                    </span>
                    <span className="ann-card__domain">{annotation.domainLabel}</span>
                    <span className="ann-card__room">{annotation.room}</span>
                  </div>
                  <p className="ann-card__title">{annotation.title}</p>
                  <p className="ann-card__rec">→ {annotation.recommendation}</p>
                </div>
              ) : null}
            </div>
          );
        })}

        {agentPaths.map((agent) => (
          <div
            key={agent.id}
            ref={(node) => { agentRefs.current[agent.id] = node; }}
            className="agent-dot"
            title={agent.role}
            style={{ background: agent.color, opacity: 0, visibility: "hidden" }}
          />
        ))}
      </div>

      <div className="world-brand">
        <span className="world-brand__logo">MedSentinel</span>
        <span className="world-brand__sub">LeTourneau University · Nursing Skills Lab · Live scan</span>
      </div>

      {liveFindings.length > 0 ? (
        <div className="world-ticker">
          {liveFindings.map((finding, index) => (
            <div
              key={finding.id}
              className={`world-tick world-tick--${finding.sev.toLowerCase()}`}
              style={{ opacity: 1 - index * 0.18 }}
            >
              <span className="world-tick__sev">{finding.sev}</span>
              {finding.text.slice(0, 72)}
              {finding.text.length > 72 ? "…" : ""}
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
          <span className="world-stat__num">{agentPaths.length}</span>
          <span className="world-stat__label">Agents active</span>
        </div>
        <a href="/dashboard" className="world-cta">
          Open dashboard →
        </a>
      </div>
    </div>
  );
}
