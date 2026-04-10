import type {
  CoverageMap,
  Facility,
  FacilityCreateInput,
  Finding,
  ModelStatusResponse,
  RunSimulationResponse,
  Scan,
  ScenarioSimulation,
  Unit,
  WorldModel
} from "@/types";

import { API_BASE } from "@/lib/runtime";

async function parse<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  let response: Response;

  try {
    response = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      },
      cache: "no-store"
    });
  } catch (error) {
    throw new Error(
      `Unable to reach MedSentinel backend at ${API_BASE}. Start the FastAPI server with \`./scripts/start-backend.sh\` from the repo root and retry.`,
      { cause: error }
    );
  }

  if (!response.ok) {
    throw new Error(`Request failed for ${path} (${response.status} ${response.statusText}) via ${url}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listFacilities: () => parse<Facility[]>("/api/facilities"),
  createFacility: (payload: FacilityCreateInput) =>
    parse<Facility>("/api/facilities", { method: "POST", body: JSON.stringify(payload) }),
  getFacility: (facilityId: string) =>
    parse<{ facility: Facility; units: Unit[]; models: WorldModel[] }>(`/api/facilities/${facilityId}`),
  getCoverage: (facilityId: string) => parse<CoverageMap>(`/api/facilities/${facilityId}/coverage`),
  triggerAcquisition: (facilityId: string) => parse(`/api/facilities/${facilityId}/acquire`, { method: "POST" }),
  getModelStatus: (unitId: string) => parse<ModelStatusResponse>(`/api/models/${unitId}/status`),
  runScan: (unitId: string) => parse<Scan>(`/api/scans/${unitId}/run`, { method: "POST" }),
  getScanStatus: (unitId: string) => parse<Scan>(`/api/scans/${unitId}/status`),
  getFindings: (unitId: string) => parse<Finding[]>(`/api/scans/${unitId}/findings`),
  getSceneGraph: (unitId: string) => parse<Record<string, unknown>>(`/api/models/${unitId}/scene_graph`),
  getSplat: (unitId: string) => parse<{ signed_url: string; stream_url?: string }>(`/api/models/${unitId}/splat`),
  runSimulation: (unitId: string, scenarioPrompt: string, agentsPerRole = 3) =>
    parse<RunSimulationResponse>(`/api/simulate/${unitId}/run`, {
      method: "POST",
      body: JSON.stringify({ scenario_prompt: scenarioPrompt, agents_per_role: agentsPerRole })
    }),
  getLatestSimulation: (unitId: string) =>
    parse<ScenarioSimulation>(`/api/simulate/${unitId}/latest`),
  listSimulations: (unitId: string) =>
    parse<ScenarioSimulation[]>(`/api/simulate/${unitId}/list`)
};
