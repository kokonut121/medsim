"use client";

/**
 * WorldViewer — primary demo component for the MedSentinel landing page.
 *
 * - Renders the hospital Gaussian-splat world model (.spz) directly in the browser
 *   using @mkkellogg/gaussian-splats-3d (no iframe / no external viewer dependency).
 * - Projects annotation world-positions through the THREE.js camera every frame
 *   so annotation pins genuinely track 3D locations as the user orbits.
 * - Streams live swarm-agent findings over WebSocket and adds them as pins.
 * - Animates agent "avatars" patrolling pre-defined 3D paths through the scene.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import * as THREE from "three";

// ---------------------------------------------------------------------------
// Fallback splat URL — proxied through our own backend to avoid R2 CORS block
// ---------------------------------------------------------------------------
const FALLBACK_SPLAT = `${
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000")
    : "http://127.0.0.1:8000"
}/api/models/unit_1/splat/stream`;

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
  /** World-space position inside the .spz scene */
  worldPos: [number, number, number];
  cardSide: "left" | "right";
}

interface AgentDef {
  id: string;
  role: string;
  color: string;
  /** Closed loop of world-space waypoints */
  path: Array<[number, number, number]>;
  speed: number; // units per second
}

interface ScreenPos {
  x: number;
  y: number;
  visible: boolean;
}

// ---------------------------------------------------------------------------
// Static annotation data — real findings from the scan + optimization run
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Swarm agent patrol paths (world-space loops)
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Colour maps
// ---------------------------------------------------------------------------
const SEV_COLOR: Record<Severity, string> = {
  CRITICAL: "#e74c3c",
  HIGH:     "#e67e22",
  ADVISORY: "#0d7e78",
};
const SEV_GLOW: Record<Severity, string> = {
  CRITICAL: "rgba(231,76,60,0.5)",
  HIGH:     "rgba(230,126,34,0.5)",
  ADVISORY: "rgba(13,126,120,0.5)",
};
const DOMAIN_COLOR: Record<string, string> = {
  ICA: "#e74c3c", ERA: "#e74c3c",
  MSA: "#e67e22", FRA: "#e67e22",
  PFA: "#0d7e78", SCA: "#5b2c8d",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert Three.js NDC → pixel coordinates within a container */
function projectToScreen(
  worldPos: [number, number, number],
  camera: THREE.PerspectiveCamera,
  w: number,
  h: number,
): ScreenPos {
  const vec = new THREE.Vector3(...worldPos).project(camera);
  return {
    x: ((vec.x + 1) / 2) * w,
    y: (-(vec.y - 1) / 2) * h,
    visible: vec.z < 1,
  };
}

/** Interpolate along a closed path given total distance travelled */
function pathPosition(
  path: Array<[number, number, number]>,
  t: number,
): [number, number, number] {
  // compute total length
  const lengths: number[] = [];
  let total = 0;
  for (let i = 0; i < path.length - 1; i++) {
    const d = Math.hypot(
      path[i + 1][0] - path[i][0],
      path[i + 1][1] - path[i][1],
      path[i + 1][2] - path[i][2],
    );
    lengths.push(d);
    total += d;
  }
  const dist = ((t % total) + total) % total;
  let acc = 0;
  for (let i = 0; i < lengths.length; i++) {
    if (acc + lengths[i] >= dist) {
      const frac = (dist - acc) / lengths[i];
      const a = path[i];
      const b = path[i + 1];
      return [
        a[0] + (b[0] - a[0]) * frac,
        a[1] + (b[1] - a[1]) * frac,
        a[2] + (b[2] - a[2]) * frac,
      ];
    }
    acc += lengths[i];
  }
  return path[0];
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface WorldViewerProps {
  initialSplatUrl?: string;
}

export function WorldViewer({ initialSplatUrl }: WorldViewerProps) {
  /** Outer shell — React owns this, used only for clientWidth/Height measurements */
  const shellRef  = useRef<HTMLDivElement>(null);
  /** Inner splat div — the viewer injects its canvas here; React never reconciles children */
  const splatRef  = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<import("@mkkellogg/gaussian-splats-3d").Viewer | null>(null);
  const rafRef       = useRef<number>(0);
  const startTimeRef = useRef<number>(performance.now());

  const [splatUrl, setSplatUrl]     = useState<string>(initialSplatUrl ?? "");
  const isIframeUrl = splatUrl.startsWith("https://marble.worldlabs.ai");
  const [loading, setLoading]       = useState(!splatUrl.startsWith("https://marble.worldlabs.ai"));
  const [error, setError]           = useState<string | null>(null);
  const [openId, setOpenId]         = useState<string | null>(null);

  // screen-space positions updated each RAF frame
  const [annPos,   setAnnPos]   = useState<Record<string, ScreenPos>>({});
  const [agentPos, setAgentPos] = useState<Record<string, ScreenPos & { role: string; color: string }>>({});

  // live findings arriving over WebSocket
  const [liveFindings, setLiveFindings] = useState<Array<{ id: string; text: string; sev: Severity }>>([]);

  // ── 1. Resolve splat URL from backend if not injected by server ────────────
  useEffect(() => {
    if (splatUrl) return;
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
    fetch(`${base}/api/models/unit_1/splat`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setSplatUrl(d?.stream_url ? `${base}${d.stream_url}` : FALLBACK_SPLAT))
      .catch(() => setSplatUrl(FALLBACK_SPLAT));
  }, [splatUrl]);

  // ── 2. Init Gaussian-splat viewer (skipped for iframe URLs) ──────────────
  useEffect(() => {
    if (!splatUrl || !splatRef.current || isIframeUrl) return;
    const splatEl = splatRef.current;
    let disposed = false;

    const init = async () => {
      try {
        setLoading(true);
        // ⚠ Do NOT call replaceChildren() here — React doesn't own splatEl's
        // children but calling replaceChildren on cleanup still races with React.

        const GS3D = await import("@mkkellogg/gaussian-splats-3d");
        if (disposed) return;

        const viewer = new GS3D.Viewer({
          rootElement:            splatEl,
          // Standard Y-up; World Labs SPZ models use conventional coordinate system
          cameraUp:               [0, 1, 0],
          initialCameraPosition:  [0, 1, 3],
          initialCameraLookAt:    [0, 0.5, 0],
          gpuAcceleratedSort:     true,
          sharedMemoryForWorkers: false,
          antialiased:            true,
        });

        await viewer.addSplatScene(splatUrl, {
          // Force .spz for all proxy/stream URLs — they don't end in .spz but they're always .spz
          format: (splatUrl.endsWith(".spz") || splatUrl.endsWith(".bin") ||
                   splatUrl.includes("/splat/stream") || splatUrl.includes("/splat/"))
            ? GS3D.SceneFormat.Spz
            : undefined,
          showLoadingUI:              false,
          splatAlphaRemovalThreshold: 1,
        });

        if (disposed) { viewer.dispose(); return; }

        viewer.start();
        viewerRef.current = viewer;
        setError(null);
      } catch (err) {
        if (!disposed)
          setError(err instanceof Error ? err.message : "Splat load failed");
      } finally {
        if (!disposed) setLoading(false);
      }
    };

    void init();
    return () => {
      disposed = true;
      viewerRef.current?.stop();
      viewerRef.current?.dispose();
      viewerRef.current = null;
      // ⚠ Do NOT call replaceChildren() — the viewer disposes its own canvas;
      // calling replaceChildren races with React's reconciler and causes
      // "removeChild: node is not a child" errors.
    };
  }, [splatUrl]);

  // ── 3. RAF loop — project annotations + agents to screen every frame ──────
  useEffect(() => {
    const tick = () => {
      rafRef.current = requestAnimationFrame(tick);
      const viewer = viewerRef.current;
      const shell = shellRef.current;
      if (!viewer?.camera || !shell) return;

      const camera = viewer.camera;
      const w = shell.clientWidth;
      const h = shell.clientHeight;

      // Annotations
      const nextAnn: Record<string, ScreenPos> = {};
      for (const ann of ANNOTATIONS)
        nextAnn[ann.id] = projectToScreen(ann.worldPos, camera, w, h);
      setAnnPos(nextAnn);

      // Swarm agents (time-driven path interpolation)
      const elapsed = (performance.now() - startTimeRef.current) / 1000;
      const nextAgent: Record<string, ScreenPos & { role: string; color: string }> = {};
      for (const ag of AGENTS) {
        const pos = pathPosition(ag.path, elapsed * ag.speed);
        const sp  = projectToScreen(pos, camera, w, h);
        nextAgent[ag.id] = { ...sp, role: ag.role, color: ag.color };
      }
      setAgentPos(nextAgent);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  // ── 4. WebSocket — live findings ──────────────────────────────────────────
  useEffect(() => {
    const wsBase = process.env.NEXT_PUBLIC_WS_URL ?? "ws://127.0.0.1:8000";
    const ws = new WebSocket(`${wsBase}/ws/scans/unit_1/live`);
    ws.onmessage = (ev) => {
      try {
        const f = JSON.parse(ev.data as string);
        setLiveFindings(prev => [
          { id: f.finding_id, text: f.label_text, sev: f.severity as Severity },
          ...prev.slice(0, 4),
        ]);
      } catch { /* ignore */ }
    };
    return () => ws.close();
  }, []);

  // ── 5. Stats ──────────────────────────────────────────────────────────────
  const critCount = ANNOTATIONS.filter(a => a.severity === "CRITICAL").length;
  const highCount = ANNOTATIONS.filter(a => a.severity === "HIGH").length;
  const advCount  = ANNOTATIONS.filter(a => a.severity === "ADVISORY").length;

  return (
    <div ref={shellRef} className="world-shell">

      {/* WorldLabs iframe viewer — used when a marble.worldlabs.ai URL is provided */}
      {isIframeUrl ? (
        <iframe
          src={splatUrl}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", border: "none" }}
          allow="xr-spatial-tracking; accelerometer; gyroscope"
          title="World reconstruction"
        />
      ) : (
        /* Gaussian-splat viewer injects its canvas here — React never reconciles children */
        <div ref={splatRef} style={{ position: "absolute", inset: 0 }} />
      )}

      {/* Loading / error states */}
      {loading && (
        <div className="world-loading">
          <div className="world-loading__ring" />
          <p>Loading world model…</p>
        </div>
      )}
      {error && !loading && (
        <div className="world-loading">
          <p style={{ color: SEV_COLOR.CRITICAL }}>⚠ {error}</p>
        </div>
      )}

      {/* Annotation + agent overlay (pointer-events delegated per element) */}
      <div className="world-overlay">

        {/* Annotation pins */}
        {ANNOTATIONS.map(ann => {
          const sp = annPos[ann.id];
          if (!sp?.visible) return null;
          const color = SEV_COLOR[ann.severity];
          const glow  = SEV_GLOW[ann.severity];
          const dc    = DOMAIN_COLOR[ann.domain] ?? color;
          const isOpen = openId === ann.id;

          return (
            <div
              key={ann.id}
              className="ann-pin"
              style={{ left: sp.x, top: sp.y, pointerEvents: "auto" }}
              onMouseEnter={() => setOpenId(ann.id)}
              onMouseLeave={() => setOpenId(null)}
              onClick={() => setOpenId(v => v === ann.id ? null : ann.id)}
            >
              {/* pulse rings — staggered */}
              <span className={`ann-pulse ann-pulse--${ann.severity.toLowerCase()}`}
                style={{ "--glow": glow } as React.CSSProperties} />
              <span className={`ann-pulse ann-pulse--${ann.severity.toLowerCase()} ann-pulse--delay`}
                style={{ "--glow": glow } as React.CSSProperties} />

              {/* dot */}
              <span className="ann-dot" style={{
                background: color,
                boxShadow: `0 0 0 2px rgba(255,255,255,.3), 0 0 12px ${glow}`,
              }} />

              {/* domain badge */}
              <span className="ann-badge" style={{ background: dc }}>{ann.domain}</span>

              {/* expanded card */}
              {isOpen && (
                <div className={`ann-card ann-card--${ann.cardSide}`}
                  style={{ "--cc": color } as React.CSSProperties}>
                  <div className="ann-card__row">
                    <span className="ann-card__sev" style={{ background: color }}>{ann.severity}</span>
                    <span className="ann-card__domain">{ann.domainLabel}</span>
                    <span className="ann-card__room">{ann.room}</span>
                  </div>
                  <p className="ann-card__title">{ann.title}</p>
                  <p className="ann-card__rec">→ {ann.recommendation}</p>
                </div>
              )}
            </div>
          );
        })}

        {/* Swarm agent dots */}
        {Object.entries(agentPos).map(([id, sp]) => {
          if (!sp.visible) return null;
          return (
            <div
              key={id}
              className="agent-dot"
              title={sp.role}
              style={{ left: sp.x, top: sp.y, background: sp.color }}
            />
          );
        })}
      </div>

      {/* Brand bar */}
      <div className="world-brand">
        <span className="world-brand__logo">MedSentinel</span>
        <span className="world-brand__sub">Northwestern Memorial · Trauma Center · Live scan</span>
      </div>

      {/* Live findings ticker */}
      {liveFindings.length > 0 && (
        <div className="world-ticker">
          {liveFindings.map((f, i) => (
            <div key={f.id} className={`world-tick world-tick--${f.sev.toLowerCase()}`}
              style={{ opacity: 1 - i * 0.18 }}>
              <span className="world-tick__sev">{f.sev}</span>
              {f.text.slice(0, 72)}{f.text.length > 72 ? "…" : ""}
            </div>
          ))}
        </div>
      )}

      {/* Stats bar */}
      <div className="world-stats">
        <div className="world-stat world-stat--critical">
          <span className="world-stat__num">{critCount}</span>
          <span className="world-stat__label">Critical</span>
        </div>
        <div className="world-stat world-stat--high">
          <span className="world-stat__num">{highCount}</span>
          <span className="world-stat__label">High</span>
        </div>
        <div className="world-stat world-stat--advisory">
          <span className="world-stat__num">{advCount}</span>
          <span className="world-stat__label">Advisory</span>
        </div>
        <div className="world-stat world-stat--gain">
          <span className="world-stat__num">+5%</span>
          <span className="world-stat__label">Efficiency gain</span>
        </div>
        <div className="world-stat">
          <span className="world-stat__num">{AGENTS.length}</span>
          <span className="world-stat__label">Agents active</span>
        </div>
        <a href="/dashboard" className="world-cta">Open dashboard →</a>
      </div>
    </div>
  );
}
