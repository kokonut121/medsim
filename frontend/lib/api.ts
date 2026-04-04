import type { CoverageMap, Facility, Finding, Scan, WorldModel } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function parse<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Request failed for ${path}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listFacilities: () => parse<Facility[]>("/api/facilities"),
  getFacility: (facilityId: string) => parse<{ facility: Facility; units: any[]; models: WorldModel[] }>(`/api/facilities/${facilityId}`),
  getCoverage: (facilityId: string) => parse<CoverageMap>(`/api/facilities/${facilityId}/coverage`),
  triggerAcquisition: (facilityId: string) => parse(`/api/facilities/${facilityId}/acquire`, { method: "POST" }),
  runScan: (unitId: string) => parse<Scan>(`/api/scans/${unitId}/run`, { method: "POST" }),
  getScanStatus: (unitId: string) => parse<Scan>(`/api/scans/${unitId}/status`),
  getFindings: (unitId: string) => parse<Finding[]>(`/api/scans/${unitId}/findings`),
  getSceneGraph: (unitId: string) => parse<Record<string, unknown>>(`/api/models/${unitId}/scene_graph`),
  getSplat: (unitId: string) => parse<{ signed_url: string }>(`/api/models/${unitId}/splat`)
};

