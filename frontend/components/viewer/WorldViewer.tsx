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
  cruiseHeight: number;
  bobAmplitude: number;
  bobRate: number;
  bobPhase: number;
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

// Paper plane geometry — parsed from docs/paper-plane-asset.obj (SketchUp export).
// Vertices normalized to ~0.3 m wingspan, nose pointing +X, wings spread ±Z.
// Y is negated from raw OBJ (SketchUp Y-up → Three.js Y-up after flip for correct orientation).
const PLANE_S = 0.3;
const PLANE_VERTS: Array<[number, number, number]> = (
  [
    [-0.500,  0.054,  0.000],  // v1 — keel tip (top in Three.js after negate)
    [-0.500, -0.054,  0.018],  // v2
    [ 0.500, -0.054,  0.000],  // v3 — nose tip
    [-0.500, -0.054,  0.288],  // v4
    [-0.500, -0.040,  0.036],  // v5
    [-0.500, -0.054, -0.018],  // v6
    [-0.500, -0.054, -0.288],  // v7
    [-0.500, -0.040, -0.036],  // v8
  ] as Array<[number, number, number]>
).map(([x, y, z]) => [x * PLANE_S, y * PLANE_S - 0.02, z * PLANE_S]);
//                                              ↑ shift model down so visual centre matches track height

const PLANE_FACES: Array<{ vi: [number, number, number]; nx: number; ny: number; nz: number }> = [
  { vi: [0, 1, 2], nx: -0.018, ny: -0.165, nz: -0.986 },
  { vi: [1, 3, 2], nx:  0,     ny: -1,     nz:  0     },
  { vi: [3, 4, 2], nx:  0.015, ny:  0.998, nz:  0.053 },
  { vi: [5, 0, 2], nx: -0.018, ny: -0.165, nz:  0.986 },
  { vi: [6, 5, 2], nx:  0,     ny: -1,     nz:  0     },
  { vi: [2, 7, 6], nx:  0.015, ny:  0.998, nz: -0.053 },
];

const PLANE_LIGHT = new THREE.Vector3(0.416, 0.832, 0.249); // above-right key light
const PLANE_NOSE = new THREE.Vector3(1, 0, 0);
const _pq = new THREE.Quaternion();
const _pv = new THREE.Vector3();
const _pn = new THREE.Vector3();

function drawAgentPlane(
  ctx: CanvasRenderingContext2D,
  worldPos: THREE.Vector3,
  travelDir: THREE.Vector3,
  color: string,
  camera: THREE.PerspectiveCamera,
  width: number,
  height: number,
): void {
  const dir = _pv.copy(travelDir).setY(0);
  if (dir.lengthSq() > 0.0001) {
    _pq.setFromUnitVectors(PLANE_NOSE, dir.normalize());
  } else {
    _pq.identity();
  }

  // transform verts to world space
  const wv = PLANE_VERTS.map(([lx, ly, lz]) =>
    new THREE.Vector3(lx, ly, lz).applyQuaternion(_pq).add(worldPos),
  );
  const sv = wv.map((v) => projectToScreen(v, camera, width, height));
  if (!sv.some((s) => s.visible)) return;

  // painter's sort — depth in camera space
  const camInv = camera.matrixWorldInverse;
  const sorted = PLANE_FACES.map((face) => {
    const z = face.vi.reduce((s, i) => s + new THREE.Vector3().copy(wv[i]).applyMatrix4(camInv).z, 0) / 3;
    return { face, z };
  }).sort((a, b) => a.z - b.z);

  const ri = parseInt(color.slice(1, 3), 16);
  const gi = parseInt(color.slice(3, 5), 16);
  const bi = parseInt(color.slice(5, 7), 16);

  ctx.globalAlpha = 0.93;
  for (const { face } of sorted) {
    const [i0, i1, i2] = face.vi;
    if (!sv[i0].visible && !sv[i1].visible && !sv[i2].visible) continue;
    _pn.set(face.nx, face.ny, face.nz).applyQuaternion(_pq);
    const br = Math.max(0, _pn.dot(PLANE_LIGHT)) * 0.65 + 0.35;
    ctx.beginPath();
    ctx.moveTo(sv[i0].x, sv[i0].y);
    ctx.lineTo(sv[i1].x, sv[i1].y);
    ctx.lineTo(sv[i2].x, sv[i2].y);
    ctx.closePath();
    ctx.fillStyle = `rgb(${Math.round(ri * br)},${Math.round(gi * br)},${Math.round(bi * br)})`;
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.12)";
    ctx.lineWidth = 0.5;
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
}

const TARGET_OVERLAY_FPS = 30;
const LIVE_FINDINGS_LIMIT = 5;
// ~2 seconds of motion at TARGET_OVERLAY_FPS — length of the dotted contrail.
const AGENT_TRAIL_SAMPLES = 60;
const UNIT_ID = "unit_1";

// Grid → world coordinate mapping (must match backend team_utils.py)
const GRID_SCALE = 0.8;
const COL_ORIGIN = 2.0;
const ROW_ORIGIN = 1.5;

function gridToWorld(col: number, row: number, height = 1.0): [number, number, number] {
  return [(col - COL_ORIGIN) * GRID_SCALE, height, (row - ROW_ORIGIN) * GRID_SCALE];
}

const AGENT_ROLES = [
  { role: "nurse", color: "#27ae60", speed: 0.55, cruiseHeight: 1.5, bobAmplitude: 0.08, bobRate: 1.2, bobPhase: 0.0 },
  { role: "nurse", color: "#27ae60", speed: 0.48, cruiseHeight: 1.5, bobAmplitude: 0.1, bobRate: 1.0, bobPhase: 0.9 },
  { role: "instructor", color: "#2980b9", speed: 0.65, cruiseHeight: 1.5, bobAmplitude: 0.12, bobRate: 1.3, bobPhase: 1.7 },
  { role: "emergency_responder", color: "#c0392b", speed: 1.05, cruiseHeight: 1.5, bobAmplitude: 0.09, bobRate: 1.6, bobPhase: 2.4 },
  { role: "supply_staff", color: "#8e44ad", speed: 0.38, cruiseHeight: 1.5, bobAmplitude: 0.06, bobRate: 0.85, bobPhase: 3.1 },
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
  const sortedCorridors = corridors.sort((a, b) => {
    const aCol = (a.grid_col as number) ?? 0;
    const bCol = (b.grid_col as number) ?? 0;
    return aCol - bCol;
  });

  return AGENT_ROLES.map((roleInfo, i) => {
    const corridorWaypoints: Array<[number, number, number]> = sortedCorridors.length >= 2
      ? sortedCorridors.map((r) =>
          gridToWorld(
            (r.grid_col as number) ?? 0,
            (r.grid_row as number) ?? 0,
            roleInfo.cruiseHeight,
          ),
        )
      : [
          [-1, roleInfo.cruiseHeight, -1],
          [1, roleInfo.cruiseHeight, -1],
          [1, roleInfo.cruiseHeight, 1],
          [-1, roleInfo.cruiseHeight, 1],
        ];
    const loopPath: Array<[number, number, number]> = [...corridorWaypoints, corridorWaypoints[0]];

    let path: Array<[number, number, number]>;
    if (i < 2) {
      // Nurses: follow corridor loop
      path = loopPath;
    } else if (i === 2 && patientRooms.length > 0) {
      // Instructor: visits patient/sim rooms
      const roomWaypoints = patientRooms.slice(0, 4).map((r) =>
        gridToWorld(
          (r.grid_col as number) ?? 0,
          (r.grid_row as number) ?? 0,
          roleInfo.cruiseHeight,
        ),
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
      cruiseHeight: roleInfo.cruiseHeight,
      bobAmplitude: roleInfo.bobAmplitude,
      bobRate: roleInfo.bobRate,
      bobPhase: roleInfo.bobPhase,
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
  elapsedSeconds: number,
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
      const worldY =
        start[1] +
        (end[1] - start[1]) * progress +
        Math.sin(elapsedSeconds * agent.bobRate + agent.bobPhase) * agent.bobAmplitude;

      return target.set(
        start[0] + (end[0] - start[0]) * progress,
        worldY,
        start[2] + (end[2] - start[2]) * progress,
      );
    }

    traversed += segmentLength;
  }

  const [x, y, z] = agent.path[0];
  return target.set(
    x,
    y + Math.sin(elapsedSeconds * agent.bobRate + agent.bobPhase) * agent.bobAmplitude,
    z,
  );
}

function drawAgentTrail(
  ctx: CanvasRenderingContext2D,
  history: ScreenPos[],
  position: ScreenPos,
  color: string,
) {
  if (!position.visible) {
    history.length = 0;
    return;
  }

  history.unshift(position);
  history.length = Math.min(history.length, AGENT_TRAIL_SAMPLES);

  if (history.length < 2) return;

  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  // Pass 1 — dark halo underlay so the contrail stays readable over bright
  // splat regions. Solid (no dash), slightly thicker than the colored stroke.
  ctx.setLineDash([]);
  ctx.lineWidth = 4;
  ctx.strokeStyle = "#000000";
  for (let i = 0; i < history.length - 1; i += 1) {
    const a = history[i];
    const b = history[i + 1];
    if (!a.visible || !b.visible) continue;
    const t = i / (history.length - 1);
    ctx.globalAlpha = (1 - t) * 0.5;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }

  // Pass 2 — dotted color stroke. globalAlpha ramps 0.75 → 0 head-to-tail.
  ctx.setLineDash([2, 6]);
  ctx.lineWidth = 2;
  ctx.strokeStyle = color;
  for (let i = 0; i < history.length - 1; i += 1) {
    const a = history[i];
    const b = history[i + 1];
    if (!a.visible || !b.visible) continue;
    const t = i / (history.length - 1);
    ctx.globalAlpha = (1 - t) * 0.75;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }

  ctx.globalAlpha = 1;
  ctx.setLineDash([]);
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

const ROOM_COLOR: Record<string, string> = {
  patient_room: "#1a3a4a",
  corridor_hallway: "#0d2030",
  nursing_station: "#1a3a2a",
  medication_room_pharmacy: "#2a2a1a",
  lobby_main_entrance: "#1a2a3a",
  utility_support: "#1e1e2e",
};

function FloorPlan({
  rooms,
  annotations,
}: {
  rooms: Array<{ id: string; type: string; col: number; row: number }>;
  annotations: Array<{ id: string; room: string; severity: Severity }>;
}) {
  const CELL = 110;
  const PAD = 24;
  const cols = Math.max(...rooms.map((r) => r.col)) + 1;
  const rows = Math.max(...rooms.map((r) => r.row)) + 1;
  const w = cols * CELL + PAD * 2;
  const h = rows * CELL + PAD * 2;
  const sevByRoom: Record<string, Severity> = {};
  for (const a of annotations) {
    const prev = sevByRoom[a.room];
    if (!prev || (a.severity === "CRITICAL") || (a.severity === "HIGH" && prev === "ADVISORY")) {
      sevByRoom[a.room] = a.severity;
    }
  }
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", background: "#080f14" }}
    >
      {rooms.map((room) => {
        const x = PAD + room.col * CELL;
        const y = PAD + room.row * CELL;
        const sev = sevByRoom[room.id];
        const fill = ROOM_COLOR[room.type] ?? "#111820";
        const stroke = sev === "CRITICAL" ? SEV_COLOR.CRITICAL : sev === "HIGH" ? SEV_COLOR.HIGH : "#1e3040";
        const label = room.id.replace(/^NL-/, "");
        return (
          <g key={room.id}>
            <rect x={x + 3} y={y + 3} width={CELL - 6} height={CELL - 6} rx={6} fill={fill} stroke={stroke} strokeWidth={sev ? 2 : 1} />
            <text x={x + CELL / 2} y={y + CELL / 2 - 6} textAnchor="middle" fill="#4a7a9b" fontSize={10} fontFamily="monospace">{label}</text>
            <text x={x + CELL / 2} y={y + CELL / 2 + 10} textAnchor="middle" fill="#2a4a5a" fontSize={8} fontFamily="monospace">{room.type.replace(/_/g, " ")}</text>
            {sev && (
              <circle cx={x + CELL - 14} cy={y + 14} r={6} fill={SEV_COLOR[sev]} opacity={0.9} />
            )}
          </g>
        );
      })}
    </svg>
  );
}

export function WorldViewer({ initialSplatUrl }: WorldViewerProps) {
  const shellRef = useRef<HTMLDivElement>(null);
  const splatRef = useRef<HTMLDivElement>(null);
  const trailCanvasRef = useRef<HTMLCanvasElement>(null);
  const annotationRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const agentRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const agentTrailHistoryRef = useRef<Record<string, ScreenPos[]>>({});
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
  const [floorRooms, setFloorRooms] = useState<Array<{ id: string; type: string; col: number; row: number }>>([]);

  const isIframeUrl = splatUrl.startsWith("https://marble.worldlabs.ai");
  const noModel = splatUrl === "";
  const { viewerRef, loading: gaussianLoading, error } = useGaussianSplatViewer(
    isIframeUrl || noModel ? "" : splatUrl,
    splatRef,
  );
  const loading = !noModel && !isIframeUrl && gaussianLoading;

  // Load splat URL
  useEffect(() => {
    if (splatUrl) return;
    let cancelled = false;

    fetch(buildApiUrl(`/api/models/${UNIT_ID}/splat`), { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((payload) => {
        if (cancelled) return;
        setSplatUrl(payload ? resolveSplatAssetUrl(payload as { signed_url: string; stream_url?: string }) : "");
      })
      .catch(() => { if (!cancelled) setSplatUrl(""); });

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
            fetch(buildApiUrl(`/api/scans/${UNIT_ID}/run`), { method: "POST" }).catch(() => null);
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

  useEffect(() => {
    agentTrailHistoryRef.current = {};
  }, [agentPaths]);

  // Load scene graph → build agent patrol paths
  useEffect(() => {
    let cancelled = false;

    fetch(buildApiUrl(`/api/models/${UNIT_ID}/scene_graph`), { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((sg: Record<string, unknown> | null) => {
        if (cancelled || !sg) return;
        const rooms = (sg.rooms as Array<Record<string, unknown>>) ?? [];
        setAgentPaths(buildAgentPaths(rooms));
        setFloorRooms(rooms.map((r) => ({
          id: r.room_id as string,
          type: r.type as string,
          col: (r.grid_col as number) ?? 0,
          row: (r.grid_row as number) ?? 0,
        })));
      })
      .catch(() => null);

    return () => { cancelled = true; };
  }, []);

  // Shell resize observer — also keeps the trail canvas backing store in sync.
  useEffect(() => {
    const shell = shellRef.current;
    if (!shell) return;
    const updateSize = () => {
      const width = shell.clientWidth;
      const height = shell.clientHeight;
      shellSizeRef.current = { width, height };

      const canvas = trailCanvasRef.current;
      if (canvas) {
        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        const ctx = canvas.getContext("2d");
        // setTransform resets each time we set canvas.width/height, so re-apply
        // the DPR scale here. Drawing then happens in CSS-pixel coordinates.
        if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }
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
    const aheadVector = new THREE.Vector3();
    let lastPaint = 0;

    const tick = (now: number) => {
      frameRef.current = requestAnimationFrame(tick);

      if (document.hidden || now - lastPaint < 1000 / TARGET_OVERLAY_FPS) return;
      lastPaint = now;

      const viewer = viewerRef.current;
      const { width, height } = shellSizeRef.current;
      if (!viewer?.camera || width === 0 || height === 0) return;

      const trailCtx = trailCanvasRef.current?.getContext("2d") ?? null;
      if (trailCtx) trailCtx.clearRect(0, 0, width, height);

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
        const dist = elapsedSeconds * agent.speed;
        // agentVector holds world position — must NOT be passed to projectToScreen
        // before drawAgentPlane, because THREE.Vector3.project() mutates in-place.
        interpolatePath(agent, dist, elapsedSeconds, agentVector);
        interpolatePath(agent, dist + 0.08, elapsedSeconds, aheadVector);
        const travelDir = aheadVector.clone().sub(agentVector);

        // Draw 3D model first (needs world-space agentVector intact).
        if (trailCtx) {
          drawAgentPlane(trailCtx, agentVector, travelDir, agent.color, viewer.camera, width, height);
        }

        // projectToScreen mutates agentVector → only use screenPosition after this point.
        const screenPosition = projectToScreen(agentVector, viewer.camera, width, height);
        const trailHistory = agentTrailHistoryRef.current[agent.id] ?? [];
        agentTrailHistoryRef.current[agent.id] = trailHistory;
        if (trailCtx) {
          drawAgentTrail(trailCtx, trailHistory, screenPosition, agent.color);
        } else if (!screenPosition.visible) {
          trailHistory.length = 0;
        }
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
        const msg = JSON.parse(event.data as string) as {
          type: string;
          finding_id: string;
          label_text: string;
          severity: Severity;
        };

        if (msg.type !== "finding") return;

        const finding = msg;
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

      {noModel && floorRooms.length > 0 ? (
        <FloorPlan rooms={floorRooms} annotations={annotations} />
      ) : noModel ? (
        <div className="world-loading">
          <div className="world-loading__ring" />
          <p>Loading floor plan…</p>
        </div>
      ) : loading ? (
        <div className="world-loading">
          <div className="world-loading__ring" />
          <p>Loading world model…</p>
        </div>
      ) : error ? (
        <div className="world-loading">
          <p style={{ color: SEV_COLOR.CRITICAL }}>⚠ {error}</p>
        </div>
      ) : null}

      <canvas ref={trailCanvasRef} className="agent-trail-canvas" />

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
          <div key={agent.id} ref={(node) => { agentRefs.current[agent.id] = node; }} />
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
              className={`world-tick world-tick--${(finding.sev ?? "advisory").toLowerCase()}`}
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
