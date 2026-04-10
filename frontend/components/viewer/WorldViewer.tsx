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

const ANNOTATIONS: AnnotationDef[] = [
  {
    id: "a1",
    severity: "CRITICAL",
    domain: "ICA",
    domainLabel: "Infection Control",
    room: "TC-RESUS",
    title: "Resuscitation room has no crash cart",
    recommendation: "Stage a dedicated crash cart inside TC-RESUS.",
    worldPos: [-1.2, 0.3, 1.0],
    cardSide: "right",
  },
  {
    id: "a2",
    severity: "CRITICAL",
    domain: "ICA",
    domainLabel: "Infection Control",
    room: "TC-CORRIDOR",
    title: "Crash cart in far-end alcove — 45 s extra travel",
    recommendation: "Relocate to TC-SUPPLY junction for sub-15 s access.",
    worldPos: [1.5, 0.1, 2.2],
    cardSide: "left",
  },
  {
    id: "a3",
    severity: "HIGH",
    domain: "ERA",
    domainLabel: "Emergency Response",
    room: "TB-3",
    title: "Call light absent from Trauma Bay 3",
    recommendation: "Install call light connected to TC-NS display.",
    worldPos: [2.0, 0.5, 0.0],
    cardSide: "left",
  },
  {
    id: "a4",
    severity: "HIGH",
    domain: "ICA",
    domainLabel: "Infection Control",
    room: "TB-2",
    title: "Hand hygiene dispenser inaccessible",
    recommendation: "Clear obstruction or mount second dispenser at door.",
    worldPos: [0.8, 0.8, -1.5],
    cardSide: "left",
  },
  {
    id: "a5",
    severity: "ADVISORY",
    domain: "FRA",
    domainLabel: "Fall Risk",
    room: "TC-NS",
    title: "No sightline to trauma bays TB-1 / TB-2",
    recommendation: "Add glass partition or camera feed.",
    worldPos: [-0.4, 0.6, -0.8],
    cardSide: "right",
  },
  {
    id: "a6",
    severity: "ADVISORY",
    domain: "PFA",
    domainLabel: "Patient Flow",
    room: "TC-CORRIDOR",
    title: "Clean + dirty traffic merge at corridor centre",
    recommendation: "Mark dedicated east/west lanes with floor markings.",
    worldPos: [-1.8, 0.0, 2.5],
    cardSide: "right",
  },
];

const AGENTS: AgentDef[] = [
  {
    id: "nurse-1",
    role: "nurse",
    color: "#27ae60",
    path: [[-1, 0, 1], [0, 0, 2], [1, 0, 1], [0, 0, -0.5], [-1, 0, 1]],
    speed: 0.6,
  },
  {
    id: "nurse-2",
    role: "nurse",
    color: "#27ae60",
    path: [[1, 0, 0], [0.5, 0, -1], [-0.5, 0, -1], [-1, 0, 0], [1, 0, 0]],
    speed: 0.5,
  },
  {
    id: "doctor-1",
    role: "doctor",
    color: "#2980b9",
    path: [[0, 0, 2.5], [1.5, 0, 1.5], [1.5, 0, 0], [0, 0, -1], [0, 0, 2.5]],
    speed: 0.7,
  },
  {
    id: "responder-1",
    role: "emergency_responder",
    color: "#c0392b",
    path: [[-2, 0, 2], [-1, 0, 0], [0, 0, 1], [1, 0, 2], [-2, 0, 2]],
    speed: 1.1,
  },
  {
    id: "supply-1",
    role: "supply_staff",
    color: "#8e44ad",
    path: [[-0.5, 0, 2.5], [-1.5, 0, 1], [-1.5, 0, -0.5], [0, 0, 0], [-0.5, 0, 2.5]],
    speed: 0.4,
  },
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

const ANNOTATION_COUNTS = ANNOTATIONS.reduce(
  (counts, annotation) => {
    counts[annotation.severity] += 1;
    return counts;
  },
  { CRITICAL: 0, HIGH: 0, ADVISORY: 0 } satisfies Record<Severity, number>,
);

const AGENT_PATHS: AgentPathDef[] = AGENTS.map((agent) => {
  const segmentLengths: number[] = [];
  let totalLength = 0;

  for (let index = 0; index < agent.path.length - 1; index += 1) {
    const current = agent.path[index];
    const next = agent.path[index + 1];
    const length = Math.hypot(
      next[0] - current[0],
      next[1] - current[1],
      next[2] - current[2],
    );
    segmentLengths.push(length);
    totalLength += length;
  }

  return {
    ...agent,
    segmentLengths,
    totalLength,
  };
});

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

  const isIframeUrl = splatUrl.startsWith("https://marble.worldlabs.ai");
  const { viewerRef, loading: gaussianLoading, error } = useGaussianSplatViewer(
    isIframeUrl ? "" : splatUrl,
    splatRef,
  );
  const loading = !splatUrl || (!isIframeUrl && gaussianLoading);

  useEffect(() => {
    if (splatUrl) {
      return;
    }

    let cancelled = false;
    const fallback = getFallbackSplatUrl(UNIT_ID);

    fetch(buildApiUrl(`/api/models/${UNIT_ID}/splat`), { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => {
        if (cancelled) {
          return;
        }

        if (!payload) {
          setSplatUrl(fallback);
          return;
        }

        setSplatUrl(
          resolveSplatAssetUrl(
            payload as { signed_url: string; stream_url?: string },
          ),
        );
      })
      .catch(() => {
        if (!cancelled) {
          setSplatUrl(fallback);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [splatUrl]);

  useEffect(() => {
    const shell = shellRef.current;

    if (!shell) {
      return;
    }

    const updateSize = () => {
      shellSizeRef.current = {
        width: shell.clientWidth,
        height: shell.clientHeight,
      };
    };

    updateSize();

    const observer = new ResizeObserver(updateSize);
    observer.observe(shell);

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (isIframeUrl || loading || error) {
      return;
    }

    startTimeRef.current = performance.now();
    const annotationVector = new THREE.Vector3();
    const agentVector = new THREE.Vector3();
    let lastPaint = 0;

    const tick = (now: number) => {
      frameRef.current = requestAnimationFrame(tick);

      if (document.hidden || now - lastPaint < 1000 / TARGET_OVERLAY_FPS) {
        return;
      }

      lastPaint = now;
      const viewer = viewerRef.current;
      const { width, height } = shellSizeRef.current;

      if (!viewer?.camera || width === 0 || height === 0) {
        return;
      }

      for (const annotation of ANNOTATIONS) {
        annotationVector.set(...annotation.worldPos);
        updateProjectedElement(
          annotationRefs.current[annotation.id],
          projectToScreen(annotationVector, viewer.camera, width, height),
          "auto",
        );
      }

      const elapsedSeconds = (now - startTimeRef.current) / 1000;

      for (const agent of AGENT_PATHS) {
        const worldPosition = interpolatePath(
          agent,
          elapsedSeconds * agent.speed,
          agentVector,
        );

        updateProjectedElement(
          agentRefs.current[agent.id],
          projectToScreen(worldPosition, viewer.camera, width, height),
          "none",
        );
      }
    };

    frameRef.current = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(frameRef.current);
  }, [error, isIframeUrl, loading, viewerRef]);

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
          {
            id: finding.finding_id,
            text: finding.label_text,
            sev: finding.severity,
          },
          ...current.filter((item) => item.id !== finding.finding_id),
        ].slice(0, LIVE_FINDINGS_LIMIT));
      } catch {
        // Ignore malformed development events.
      }
    };

    return () => ws.close();
  }, []);

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
        {ANNOTATIONS.map((annotation) => {
          const color = SEV_COLOR[annotation.severity];
          const glow = SEV_GLOW[annotation.severity];
          const domainColor = DOMAIN_COLOR[annotation.domain] ?? color;
          const isOpen = openId === annotation.id;

          return (
            <div
              key={annotation.id}
              ref={(node) => {
                annotationRefs.current[annotation.id] = node;
              }}
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

        {AGENT_PATHS.map((agent) => (
          <div
            key={agent.id}
            ref={(node) => {
              agentRefs.current[agent.id] = node;
            }}
            className="agent-dot"
            title={agent.role}
            style={{ background: agent.color, opacity: 0, visibility: "hidden" }}
          />
        ))}
      </div>

      <div className="world-brand">
        <span className="world-brand__logo">MedSentinel</span>
        <span className="world-brand__sub">Northwestern Memorial · Trauma Center · Live scan</span>
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
          <span className="world-stat__num">{ANNOTATION_COUNTS.CRITICAL}</span>
          <span className="world-stat__label">Critical</span>
        </div>
        <div className="world-stat world-stat--high">
          <span className="world-stat__num">{ANNOTATION_COUNTS.HIGH}</span>
          <span className="world-stat__label">High</span>
        </div>
        <div className="world-stat world-stat--advisory">
          <span className="world-stat__num">{ANNOTATION_COUNTS.ADVISORY}</span>
          <span className="world-stat__label">Advisory</span>
        </div>
        <div className="world-stat world-stat--gain">
          <span className="world-stat__num">+5%</span>
          <span className="world-stat__label">Efficiency gain</span>
        </div>
        <div className="world-stat">
          <span className="world-stat__num">{AGENT_PATHS.length}</span>
          <span className="world-stat__label">Agents active</span>
        </div>
        <a href="/dashboard" className="world-cta">
          Open dashboard →
        </a>
      </div>
    </div>
  );
}
