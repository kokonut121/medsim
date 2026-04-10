# MedSentinel — Product Requirements Document

> AI World Model + Agent Orchestration Network for Hospital Safety & Operations Intelligence  
> Version 1.1 | Built for Harvard's HSIL Hackathon

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Problem Domains — Six Clinically Grounded Harm Categories](#2-problem-domains)
3. [System Architecture](#3-system-architecture)
4. [InterSystems IRIS for Health — Data Security Layer](#4-intersystems-iris-for-health)
5. [World Model Pipeline — Public Imagery First](#5-world-model-pipeline)
6. [Agent Orchestration Layer](#6-agent-orchestration-layer)
7. [Frontend Specification](#7-frontend-specification)
8. [Backend and API Specification](#8-backend-and-api-specification)
9. [Data Models](#9-data-models)
10. [Agent Prompting Strategy](#10-agent-prompting-strategy)
11. [Environment Variables](#11-environment-variables)
12. [Project File Structure](#12-project-file-structure)
13. [Implementation Roadmap](#13-implementation-roadmap)
14. [Key Risks and Mitigations](#14-key-risks-and-mitigations)

---

## 1. Product Overview

MedSentinel constructs a navigable 3D world model of any hospital facility from **publicly available imagery** (Google Street View, Google Places Photos, OpenStreetMap) — no manual bulk photo upload required — then deploys six specialized AI agent teams into that model to identify, annotate, and rank critical safety weaknesses.

All data is secured through **InterSystems IRIS for Health**, which provides HIPAA-grade encryption (Secure Wallet), FHIR R4 interoperability, role-based access control, and full audit logging as a native healthcare data platform.

MedSentinel is built on top of the World Labs Gaussian-splat world model libraries, combining Google Street View image acquisition, Modal-hosted agent teams, Redis pub/sub consensus aggregation, and a React Three Fiber frontend — with hospital-domain agent specialization and InterSystems IRIS as the data security backbone.

### Core Value Proposition

- Any hospital safety officer selects their facility on a map → the system automatically acquires imagery → generates a 3D world model → deploys agents → delivers annotated findings in under 30 minutes
- No manual photography. No bulk upload. No IT integration required for basic function.
- Findings are spatially anchored in the 3D model with plain-language labels a clinician can act on immediately
- All findings exportable as FHIR DiagnosticReport resources for EHR integration via InterSystems Health Connect Cloud

---

## 2. Problem Domains

Each of the six domains maps to a documented, high-mortality, spatially-detectable problem in hospital environments.

| Domain | Annual US Impact | Key Spatial Risk Factors |
|--------|-----------------|--------------------------|
| Hospital-Acquired Infections (HAIs) | ~99,000 deaths, $28–45B cost | Hand hygiene station placement, isolation room proximity, clean/dirty traffic separation |
| Medication Errors | 1.5M harmed, $21B cost | ADC placement, prep area lighting, distraction exposure, handoff workstation access |
| Patient Falls | 11,000 deaths, 250,000 injuries | Bedside clearance width, call light position, bathroom routing, nursing station sightlines |
| Code Blue Response Failures | Survival drops 7–10% per delayed minute | Crash cart coverage radius, AED accessibility, corridor obstructions, elevator dependency |
| ED Overcrowding / Boarding | $1.7B/yr; +1.3% mortality per boarding hour | Bed topology, transfer pathway distance, OR turnover routing, discharge corridor bottlenecks |
| Staff Communication / Handoff Failure | 70% of TJC sentinel events involve communication failure | Handoff zone infrastructure, nurse-to-patient walking distance, quiet zone absence |

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 0: InterSystems IRIS for Health                          │
│  (Secure Wallet · FHIR R4 · RBAC · Audit Log · IntegratedML)   │
├──────────────┬──────────────────────────┬───────────────────────┤
│  Layer 1     │  Layer 2                 │  Layer 3              │
│  Image       │  World Model Pipeline    │  Agent Orchestration  │
│  Acquisition │  Claude Vision →         │  6 Domain Teams       │
│  ────────    │  Scene Graph →           │  Modal (A10G)         │
│  Street View │  World Labs API →        │  Redis Pub/Sub        │
│  Places API  │  .splat binary           │  CSE Synthesis        │
│  OSM         │                          │                       │
├──────────────┴──────────────────────────┴───────────────────────┤
│  Layer 4: Frontend                                              │
│  Next.js · Mapbox · React Three Fiber · SparkJS · WebSockets   │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Selection Rationale

**Why InterSystems IRIS for Health over PostgreSQL:** General-purpose databases require significant bespoke engineering to achieve HIPAA-grade security, healthcare interoperability, and regulatory audit capability. IRIS provides all three natively, including Secure Wallet AES-256 encryption at rest, FHIR R4 repository with REST APIs, full audit logging, and IntegratedML for in-database analytics — satisfying 45 CFR §164.312 without additional engineering.

**Why Google Street View + Places over manual upload:** Any building can be world-modeled from publicly available imagery using the World Labs Marble API. Requiring hospitals to photograph and upload 200+ interior images creates an infeasible onboarding burden. Street View + Places Photos provides exterior panoramas and user-contributed interior shots for most large hospitals with zero manual effort. Supplemental uploads fill specific gaps only.

**Why Gaussian splatting (World Labs API):** Photorealistic surface detail preserved at browser-navigable frame rates. A clinician verifying "is that hand sanitizer dispenser actually on the correct side of the door" needs to see the real surface, not a low-poly geometry placeholder.

---

## 4. InterSystems IRIS for Health

### 4.1 Deployment

Use the `iris-lockeddown` container image from the InterSystems Container Registry. This image pre-configures OS-level permission hardening and disables web access to the management portal.

```yaml
# docker-compose.yml (IRIS service)
iris:
  image: containers.intersystems.com/intersystems/irishealth:2026.1-em-lockeddown
  environment:
    - ISC_DATA_DIRECTORY=/dur/irisdata
    - ISC_CPF_FILE_NAME=/dur/iris.cpf
  volumes:
    - iris-data:/dur/irisdata
    - ./iris/iris.cpf:/dur/iris.cpf:ro
  ports:
    - "1972:1972"   # IRIS SuperServer (internal only — do not expose publicly)
    - "52773:52773" # IRIS Web Gateway (internal only)
  networks:
    - internal      # Private VPC — FastAPI service only
```

**Critical:** IRIS ports must be on an internal-only network. FastAPI accesses IRIS via `intersystems-irispython` SDK over the SuperServer port. The IRIS web gateway is never exposed to the public internet.

### 4.2 Capabilities Used

| IRIS Feature | MedSentinel Usage | Implementation |
|---|---|---|
| **Secure Wallet** | Encrypts all facility, scan, and findings data at rest using IRISSECURITY database | Initialize on first deploy: `do ##class(Security.Wallet).Create("MedSentinel")` |
| **FHIR R4 Repository** | Stores findings as `DiagnosticReport` and `Observation` FHIR resources for EHR integration | Enable via IRIS FHIR Server configuration; exposed on `/fhir/r4/` endpoint |
| **HL7 V2 / ADT Feed** | Receives optional real-time bed census from hospital system (no PHI stored — only aggregate unit occupancy) | Health Connect inbound HL7 adapter; ADT A01/A03 events → unit occupancy counter |
| **IntegratedML** | In-database unit risk trend models — trained and executed inside IRIS on findings data, no extraction needed | `CREATE MODEL UnitRiskScore PREDICTING (riskScore) FROM MedSentinel.Finding` |
| **RBAC** | Role enforcement at data layer: SafetyOfficer (all), UnitManager (unit-scoped), Auditor (read-only) | Define roles in IRIS security manager; enforced on all global access |
| **Audit Logging** | Every read/write/export logged with user, timestamp, action — required for Joint Commission documentation | Enabled in IRIS audit configuration; log shipped to SIEM |
| **Vector Search (HNSW)** | Semantic search across findings: "find all findings similar to this crash cart obstruction pattern" | Store finding text embeddings as `VECTOR(1536)` column; query with `VECTOR_DOT_PRODUCT` |
| **Health Connect Cloud** | Managed FHIR pipeline to hospital EHR (Epic/Cerner) — MedSentinel pushes DiagnosticReport on scan completion | Configure Health Connect FHIR interoperability production; target endpoint = hospital FHIR server |

### 4.3 Python Integration

```python
# backend/db/iris_client.py
import iris  # intersystems-irispython package

class IRISClient:
    def __init__(self):
        self.conn = iris.connect(
            hostname=settings.IRIS_HOST,
            port=1972,
            namespace="MEDSENT",
            username=settings.IRIS_USER,
            password=settings.IRIS_PASSWORD,
        )

    def write_finding(self, finding: Finding) -> str:
        """Write a finding to IRIS globals via Secure Wallet encrypted storage."""
        gref = iris.gref("^MedSentinel.Finding")
        finding_id = self._new_id()
        gref[finding_id] = iris.list(
            finding.scan_id,
            finding.domain,
            finding.room_id,
            finding.severity,
            finding.compound_severity,
            finding.label_text,
            json.dumps(finding.spatial_anchor),
            finding.confidence,
            json.dumps(finding.evidence_r2_keys),
            finding.recommendation,
            datetime.utcnow().isoformat(),
        )
        # Also project as FHIR DiagnosticReport
        self._project_fhir_diagnostic_report(finding_id, finding)
        return finding_id

    def _project_fhir_diagnostic_report(self, finding_id: str, finding: Finding):
        """Write finding as FHIR DiagnosticReport to IRIS FHIR repository."""
        report = {
            "resourceType": "DiagnosticReport",
            "id": finding_id,
            "status": "final",
            "code": {"text": f"MedSentinel {finding.domain} Finding"},
            "conclusion": finding.label_text,
            "conclusionCode": [{"text": finding.severity}],
        }
        requests.post(
            f"http://{settings.IRIS_HOST}:52773/fhir/r4/DiagnosticReport",
            json=report,
            auth=(settings.IRIS_USER, settings.IRIS_PASSWORD),
        )
```

### 4.4 HIPAA Compliance Controls (via IRIS)

| HIPAA Control (45 CFR §164.312) | IRIS Mechanism |
|---|---|
| Access Control §164.312(a)(1) | IRIS RBAC — role definitions in Security Manager |
| Audit Controls §164.312(b) | IRIS Audit Log — immutable, exportable |
| Integrity §164.312(c)(1) | Secure Wallet AES-256 + checksummed globals |
| Encryption at Rest §164.312(a)(2)(iv) | Secure Wallet |
| Transmission Security §164.312(e)(2)(ii) | Health Connect TLS 1.3 for all HL7/FHIR |

---

## 5. World Model Pipeline

### 5.1 Image Acquisition (Public Imagery First)

No manual bulk upload. The pipeline automatically acquires imagery for any hospital address.

#### 5.1.1 Google Street View API

```python
# backend/pipeline/image_acquisition.py
import httpx

STREET_VIEW_BASE = "https://maps.googleapis.com/maps/api/streetview"
HEADINGS = [0, 45, 90, 135, 180, 225, 270, 315]

async def fetch_street_view(lat: float, lng: float, api_key: str) -> list[bytes]:
    """Fetch 8-heading panoramic exterior coverage for a location."""
    images = []
    async with httpx.AsyncClient() as client:
        for heading in HEADINGS:
            resp = await client.get(STREET_VIEW_BASE, params={
                "location": f"{lat},{lng}",
                "heading": heading,
                "fov": 90,
                "pitch": 0,
                "size": "640x640",
                "key": api_key,
            })
            if resp.status_code == 200:
                images.append(resp.content)
    return images
```

Cost: ~$0.007/image × 8–16 images = ~$0.11–$0.21 per facility exterior. Cached in R2 indefinitely; refreshed annually.

#### 5.1.2 Google Places Photos API

```python
async def fetch_places_photos(place_id: str, api_key: str, max_photos: int = 40) -> list[bytes]:
    """Fetch user-contributed interior photos from Google Maps listing."""
    async with httpx.AsyncClient() as client:
        # Step 1: Get photo references
        details = await client.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={"place_id": place_id, "fields": "photos", "key": api_key}
        )
        photo_refs = [p["photo_reference"] for p in details.json()["result"].get("photos", [])][:max_photos]

        # Step 2: Fetch each photo
        images = []
        for ref in photo_refs:
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/place/photo",
                params={"photo_reference": ref, "maxwidth": 1600, "key": api_key}
            )
            if resp.status_code == 200:
                images.append(resp.content)
        return images
```

#### 5.1.3 OpenStreetMap Building Topology

```python
async def fetch_osm_building(lat: float, lng: float) -> dict:
    """Fetch building footprint and room topology scaffold from OSM Overpass API."""
    query = f"""
    [out:json];
    (
      way["building"](around:100,{lat},{lng});
      relation["building"](around:100,{lat},{lng});
    );
    out body geom;
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://overpass-api.de/api/interpreter", data={"data": query})
        return resp.json()
    # Returns: footprint polygon, floor count (building:levels tag),
    # room/amenity tags for spatial topology scaffold
```

#### 5.1.4 Supplemental Upload UI (Optional Gap-Fill)

After automatic acquisition, the frontend shows a **coverage map**: green = imagery acquired, amber = gap. Users upload 5–15 targeted photos only for amber zones. Handled via `tus-js-client` chunked upload to `POST /api/upload/supplemental`.

### 5.2 Image Classification (Claude Vision)

```python
# backend/pipeline/classify.py
import anthropic

CATEGORIES = [
    "building_exterior", "lobby_main_entrance", "ed_entrance_ambulance_bay",
    "corridor_hallway", "nursing_station", "patient_room",
    "medication_room_pharmacy", "icu_bay", "operating_room", "utility_support", "other"
]

async def classify_image(image_bytes: bytes, source: str) -> dict:
    """Classify a hospital image into one of 11 semantic categories."""
    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg",
                               "data": base64.b64encode(image_bytes).decode()},
                },
                {
                    "type": "text",
                    "text": f"""Classify this hospital image.
Source: {source}
Categories: {', '.join(CATEGORIES)}

Respond with JSON only:
{{"category": "<one of the categories>", "confidence": <0.0-1.0>, "notes": "<brief reason>"}}"""
                }
            ],
        }]
    )
    return json.loads(response.content[0].text)
```

### 5.3 Scene Graph Extraction

```python
async def extract_scene_graph(classified_images: list[dict], osm_topology: dict) -> dict:
    """
    Extract a structured spatial scene graph from classified images + OSM data.
    Returns a JSON scene graph encoding room nodes, equipment instances,
    adjacency edges, and flow annotations.
    """
    client = anthropic.AsyncAnthropic()
    image_summary = [{"category": img["category"], "confidence": img["confidence"],
                      "source": img["source"]} for img in classified_images]
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"""You are a hospital spatial analyst. Given this set of classified hospital images
and OSM building topology, construct a spatial scene graph.

Images: {json.dumps(image_summary)}
OSM topology: {json.dumps(osm_topology)}

Return a JSON scene graph with this schema:
{{
  "units": [{{
    "unit_id": "string",
    "unit_type": "ICU|MedSurg|ED|OR|Pharmacy|...",
    "rooms": [{{
      "room_id": "string",
      "type": "patient_room|nursing_station|corridor|...",
      "area_sqft_estimate": number,
      "equipment": [{{
        "type": "crash_cart|AED|hand_hygiene_dispenser|ADC|...",
        "position": "string description",
        "accessible": boolean,
        "confidence": number
      }}],
      "adjacency": ["room_id_1", "room_id_2"],
      "sightline_to_nursing_station": boolean,
      "image_source_quality": "street_view|places|upload|inferred"
    }}]
  }}],
  "flow_annotations": {{
    "patient_flow_paths": ["room_id sequence"],
    "staff_flow_paths": ["room_id sequence"],
    "clean_corridors": ["corridor_id"],
    "dirty_corridors": ["corridor_id"]
  }}
}}"""
        }]
    )
    return json.loads(response.content[0].text)
```

### 5.4 World Labs API Integration

```python
async def generate_world_model(images: list[bytes], scene_graph: dict) -> dict:
    """Submit image set and scene graph to World Labs API for 3D Gaussian-splat generation."""
    async with httpx.AsyncClient(timeout=1800) as client:  # 30-min timeout
        # Build multipart form
        files = [("images", (f"img_{i}.jpg", img, "image/jpeg")) for i, img in enumerate(images)]
        data = {
            "scene_graph": json.dumps(scene_graph),
            "building_type": "medical_facility",
            "model_type": "gaussian_splat_v2",
            "scene_type": "indoor_medical",
        }
        resp = await client.post(
            "https://api.worldlabs.ai/v1/worlds",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {settings.WORLD_LABS_API_KEY}"},
        )
        result = resp.json()
        # Returns: { "world_id": "...", "splat_url": "...", "scene_manifest": {...} }
        return result
```

---

## 6. Agent Orchestration Layer

### 6.1 Parallel Invocation Pattern

```python
# backend/agents/orchestrator.py
import modal
import asyncio

@modal.function(gpu="A10G", timeout=300, memory=8192, concurrency_limit=3)
def run_scan(unit_id: str, world_model_id: str):
    results = asyncio.run(_parallel_scan(unit_id, world_model_id))
    return results

async def _parallel_scan(unit_id: str, world_model_id: str):
    results = await asyncio.gather(
        ica_team.remote.aio(world_model_id),   # Infection Control
        msa_team.remote.aio(world_model_id),   # Medication Safety
        fra_team.remote.aio(world_model_id),   # Fall Risk
        era_team.remote.aio(world_model_id),   # Emergency Response
        pfa_team.remote.aio(world_model_id),   # Patient Flow
        sca_team.remote.aio(world_model_id),   # Staff Communication
    )
    findings = consensus_synthesis_engine(results)
    await publish_findings_to_iris_and_redis(unit_id, findings)
    return findings
```

Each Modal function streams partial findings to Redis as they complete — not batched at the end. This enables the WebSocket feed to show real-time results within 2–3 minutes of scan start.

### 6.2 Agent Team Definitions

Each team receives: (1) the scene graph JSON, (2) perspective-correct screenshots rendered from navigation waypoints in the splat model, (3) a domain-specific system prompt.

#### Infection Control Agent Team (ICA)

**Sub-agents:** HAI-Scout, Isolation-Auditor, Traffic-Mapper

```python
ICA_SYSTEM_PROMPT = """You are a Board-Certified Infection Control Practitioner with 15 years of 
experience in acute care hospital environment audits, specializing in HAI prevention under CDC and 
APIC guidelines.

TASK:
1. HAI-Scout: For every patient room and corridor in the scene graph, identify whether a hand hygiene 
   dispenser is present within 3 feet of the room entry threshold. Flag missing or mispositioned dispensers.
2. Isolation-Auditor: Identify negative-pressure isolation rooms from door hardware and signage. 
   Calculate isolation room-to-patient-bed ratio. Flag units below CDC minimums (1:10 general, 1:4 ICU).
3. Traffic-Mapper: Identify corridor intersections where clean supply paths and soiled linen/waste paths 
   converge without physical separation. Flag each convergence point.

OUTPUT FORMAT (strict JSON array, no preamble):
[{
  "sub_agent": "HAI-Scout|Isolation-Auditor|Traffic-Mapper",
  "room_id": "string",
  "severity": "CRITICAL|HIGH|ADVISORY",
  "confidence": 0.0-1.0,
  "label_text": "max 120 chars — specific condition, location, risk. Plain clinical English.",
  "spatial_anchor": {"x": float, "y": float, "z": float},
  "recommendation": "max 200 chars — specific remediation referencing CDC/APIC guideline",
  "evidence_note": "which image or scene graph element supports this finding"
}]"""
```

#### Emergency Response Agent Team (ERA)

**Sub-agents:** CrashCart-Mapper, RRT-Pathfinder, DefibAccess-Auditor

```python
ERA_SYSTEM_PROMPT = """You are an Emergency Medicine physician and hospital safety officer specializing 
in Code Blue response optimization and rapid response team logistics.

TASK:
1. CrashCart-Mapper: For each crash cart and AED in the scene graph, compute the estimated walking-path 
   coverage radius to all patient rooms within 60 seconds at 240 feet/minute. Generate a list of patient 
   rooms NOT covered within 60 seconds. Flag each uncovered room as CRITICAL.
2. RRT-Pathfinder: For each patient room, trace the shortest pathway from the nearest nursing station. 
   Flag any pathway with: door width under 36 inches, visible corridor obstruction, or elevator dependency 
   (adds estimated 90-second delay). Calculate estimated response delay in seconds.
3. DefibAccess-Auditor: Identify AED cabinets with any visual obstruction (items stored in front, partial 
   occlusion in image). Flag each as CRITICAL.

OUTPUT FORMAT: same JSON array schema as above."""
```

#### Medication Safety Agent Team (MSA)

**Sub-agents:** ADC-Inspector, PrepZone-Auditor, Transition-Tracker

System prompt focuses on: ADC placement relative to high-acuity zones and traffic patterns, preparation area lighting and distraction exposure, handoff zone medication reconciliation infrastructure.

#### Fall Risk Agent Team (FRA)

**Sub-agents:** Room-Geometer, Sightline-Analyst, Equipment-Auditor

System prompt focuses on: bedside clearance width vs. 36-inch ANSI minimum, call light cord position relative to default bed position, nursing station visual coverage of patient rooms.

#### Patient Flow Agent Team (PFA)

**Sub-agents:** Throughput-Modeler, OR-Auditor, Discharge-Pathfinder

System prompt focuses on: inpatient-to-ED transfer path distance, OR turnover zone clean/dirty path separation, discharge corridor bottlenecks.

#### Staff Communication Agent Team (SCA)

**Sub-agents:** Handoff-Zone-Auditor, NurseStation-Geographer, Quiet-Zone-Analyzer

System prompt focuses on: handoff zone infrastructure (shared screen + acoustic separation + co-presence seating), nurse-to-patient average walking distance, acoustically separated consultation space per 20-bed cluster.

### 6.3 Consensus Synthesis Engine (CSE)

```python
# backend/agents/consensus.py

def consensus_synthesis_engine(team_results: list[list[dict]]) -> list[dict]:
    """
    Aggregate findings from all 6 agent teams.
    - Group by spatial_anchor proximity (within 5 world-units → same location)
    - Compute compound severity for co-located multi-domain findings
    - Promote compound severity >= 0.85 to CRITICAL
    - Write to IRIS, project as FHIR DiagnosticReport
    """
    all_findings = [f for team in team_results for f in team]

    # Group by spatial proximity
    location_groups = _cluster_by_spatial_anchor(all_findings, radius=5.0)

    synthesized = []
    for group in location_groups:
        domains = list({f["domain"] for f in group})
        max_severity = max(f["severity_score"] for f in group)
        compound_severity = min(1.0, max_severity + 0.15 * len(domains))

        # Intra-group confidence: 50% weight to highest-confidence finding
        confidences = sorted([f["confidence"] for f in group], reverse=True)
        weighted_confidence = 0.5 * confidences[0] + 0.5 * (
            sum(confidences[1:]) / max(len(confidences[1:]), 1)
        )

        lead = max(group, key=lambda f: f["confidence"])
        synthesized.append({
            **lead,
            "compound_severity": compound_severity,
            "severity": "CRITICAL" if compound_severity >= 0.85 else lead["severity"],
            "compound_domains": domains,
            "confidence": weighted_confidence,
        })

    return sorted(synthesized, key=lambda f: f["compound_severity"], reverse=True)


SEVERITY_SCORES = {"CRITICAL": 1.0, "HIGH": 0.7, "ADVISORY": 0.4}
```

---

## 7. Frontend Specification

### 7.1 Tech Stack

| Component | Library | Version |
|---|---|---|
| Framework | Next.js | 15 (App Router) |
| 3D Renderer | React Three Fiber + Drei | r3f v8, Drei v9 |
| Splat Engine | `@mkkellogg/gaussian-splats-3d` | 0.4.7 |
| Maps | Mapbox GL JS | v3 |
| State | Zustand | v5 |
| Styling | Tailwind CSS | v4 |
| Supplemental Upload | tus-js-client + React Dropzone | latest |
| Charts | Recharts | v2 |
| Real-time | Native WebSocket | — |

### 7.2 Page Routes

```
/                          → Landing / auth redirect
/dashboard                 → Facility map overview (all facilities)
/facility/new              → Facility onboarding (map search → auto-acquire)
/facility/[id]             → Facility detail (units list, scan history)
/facility/[id]/coverage    → Image coverage map with supplemental upload UI
/facility/[id]/model/[uid] → World model viewer (3D splat + annotation overlay)
/facility/[id]/report/[uid]→ Report export (PDF / FHIR / JSON)
```

### 7.3 World Model Viewer Component Architecture

```
WorldModelViewer (page)
├── SplatRenderer (React Three Fiber canvas, 70% width)
│   ├── SparkJSSplatMesh          # Streams .splat binary from R2 signed URL
│   ├── AnnotationOverlay         # 3D billboard system for agent findings
│   │   └── FindingBillboard[]    # Colored label per finding, anchored to spatial_anchor
│   └── CameraController          # Fly-to on finding selection; WASD navigation
├── FindingFeed (right panel, 30% width)
│   ├── DomainFilterBar           # Toggle visibility per domain
│   ├── SeveritySlider            # Filter by compound severity threshold
│   └── FindingCard[]             # Click → camera fly-to spatial anchor
│       ├── DomainBadge
│       ├── SeverityBadge
│       ├── LabelText
│       ├── RoomID
│       └── EvidenceImageThumbnail
└── AgentActivityRibbon (bottom, during active scan)
    ├── DomainProgressBar[]       # Per-domain: pending / running / complete + finding count
    └── LiveFindingFeed           # WebSocket stream of new findings as text
```

### 7.4 Domain Color Coding

```typescript
// lib/constants.ts
export const DOMAIN_COLORS = {
  ICA: "#C0392B",  // Red — Infection Control
  MSA: "#D68910",  // Amber — Medication Safety
  FRA: "#D68910",  // Amber — Fall Risk
  ERA: "#C0392B",  // Red — Emergency Response
  PFA: "#0D7E78",  // Teal — Patient Flow
  SCA: "#5B2C8D",  // Purple — Staff Communication
} as const;

export const SEVERITY_SIZES = {
  CRITICAL: 1.4,  // Billboard scale multiplier
  HIGH: 1.0,
  ADVISORY: 0.7,
} as const;
```

### 7.5 Real-time WebSocket Integration

```typescript
// hooks/useScanStream.ts
export function useScanStream(unitId: string) {
  const addFinding = useStore((s) => s.addFinding);

  useEffect(() => {
    const ws = new WebSocket(`${process.env.NEXT_PUBLIC_WS_URL}/ws/scans/${unitId}/live`);
    ws.onmessage = (event) => {
      const finding = JSON.parse(event.data);
      addFinding(finding);  // Zustand store → triggers annotation overlay update
    };
    return () => ws.close();
  }, [unitId]);
}
```

---

## 8. Backend and API Specification

### 8.1 API Routes

```python
# backend/main.py (FastAPI)

# Facilities
GET    /api/facilities
POST   /api/facilities
GET    /api/facilities/{id}
DELETE /api/facilities/{id}

# Image Acquisition
POST   /api/facilities/{id}/acquire          # Trigger Street View + Places fetch
GET    /api/facilities/{id}/coverage         # Returns coverage map JSON

# Supplemental Upload (tus resumable)
POST   /api/upload/supplemental              # tus upload endpoint
PATCH  /api/upload/supplemental/{upload_id}  # tus resume

# World Models
GET    /api/models/{unit_id}/status          # queued|enhancing|generating|ready|failed
GET    /api/models/{unit_id}/splat           # Signed R2 URL for .splat binary
GET    /api/models/{unit_id}/scene_graph     # scene_graph.json

# Scans + Agent Orchestration
POST   /api/scans/{unit_id}/run              # Trigger full 6-team agent scan
GET    /api/scans/{unit_id}/status           # Per-domain status + finding counts
GET    /api/scans/{unit_id}/findings         # All findings; ?domain=ICA&severity=CRITICAL&room_id=R101
GET    /api/scans/{unit_id}/findings/{id}    # Single finding detail

# FHIR (proxied from IRIS FHIR repository)
GET    /api/fhir/DiagnosticReport/{id}       # FHIR R4 DiagnosticReport for a scan
GET    /api/fhir/Observation/{id}            # FHIR R4 Observation for a finding
POST   /api/fhir/DiagnosticReport/$push      # Push report to external FHIR server (via Health Connect)

# Reports
GET    /api/reports/{unit_id}/pdf            # Generate + return PDF report
GET    /api/reports/{unit_id}/manifest       # findings_manifest.json download

# WebSocket
WS     /ws/scans/{unit_id}/live              # Real-time agent findings stream
```

### 8.2 Image Acquisition Job

```python
# backend/jobs/acquire_images.py
async def acquire_images_for_facility(facility_id: str, address: str):
    """Full acquisition pipeline for a new facility."""

    # 1. Geocode address
    lat, lng = await geocode(address)

    # 2. Find Google Place ID for Places Photos
    place_id = await find_place_id(address, lat, lng)

    # 3. Fetch all image sources in parallel
    street_view, places_photos, osm = await asyncio.gather(
        fetch_street_view(lat, lng, settings.GOOGLE_API_KEY),
        fetch_places_photos(place_id, settings.GOOGLE_API_KEY),
        fetch_osm_building(lat, lng),
    )

    # 4. Classify all images via Claude Vision
    all_images = street_view + places_photos
    classified = await asyncio.gather(*[
        classify_image(img, source)
        for img, source in zip(all_images, ["street_view"] * len(street_view) + ["places"] * len(places_photos))
    ])

    # 5. Upload to R2 and register S3 keys in IRIS
    for img_bytes, classification in zip(all_images, classified):
        r2_key = await upload_to_r2(img_bytes, facility_id)
        iris_client.write_image_meta(facility_id, r2_key, classification)

    # 6. Extract scene graph
    scene_graph = await extract_scene_graph(classified, osm)

    # 7. Submit to World Labs API
    world_model = await generate_world_model(all_images, scene_graph)

    # 8. Store world model reference in IRIS
    iris_client.write_world_model(facility_id, world_model)
```

---

## 9. Data Models

### 9.1 IRIS Globals Schema

```
^MedSentinel.Facility(facilityId)
  = $LB(name, address, lat, lng, orgId, googlePlaceId, osmBuildingId, createdAt)

^MedSentinel.Unit(unitId)
  = $LB(facilityId, name, floor, unitType, createdAt)

^MedSentinel.ImageMeta(imgId)
  = $LB(facilityId, r2Key, category, confidence, source, createdAt)
  source ∈ {street_view, places_photos, osm_derived, supplemental_upload}

^MedSentinel.WorldModel(modelId)
  = $LB(unitId, status, splatR2Key, sceneGraphJson, worldLabsWorldId, createdAt, completedAt)
  status ∈ {queued, acquiring, classifying, generating, ready, failed}

^MedSentinel.Scan(scanId)
  = $LB(unitId, modelId, status, triggeredAt, completedAt)
  status ∈ {queued, running, synthesizing, complete, failed}

^MedSentinel.ScanDomainStatus(scanId, domain)
  = $LB(status, findingCount, startedAt, completedAt)
  domain ∈ {ICA, MSA, FRA, ERA, PFA, SCA}

^MedSentinel.Finding(findingId)
  = $LB(scanId, domain, subAgent, roomId, severity, compoundSeverity,
        labelText, spatialAnchorJson, confidence, evidenceR2KeysJson,
        recommendation, compoundDomainsJson, createdAt)
  severity ∈ {CRITICAL, HIGH, ADVISORY}
```

### 9.2 TypeScript Types (Shared Frontend/Backend)

```typescript
// types/index.ts

export type Domain = "ICA" | "MSA" | "FRA" | "ERA" | "PFA" | "SCA";
export type Severity = "CRITICAL" | "HIGH" | "ADVISORY";
export type ModelStatus = "queued" | "acquiring" | "classifying" | "generating" | "ready" | "failed";

export interface SpatialAnchor {
  x: number;
  y: number;
  z: number;
}

export interface Finding {
  finding_id: string;
  scan_id: string;
  domain: Domain;
  sub_agent: string;
  room_id: string;
  severity: Severity;
  compound_severity: number;        // 0.0–1.0
  label_text: string;               // max 120 chars, plain clinical English
  spatial_anchor: SpatialAnchor;
  confidence: number;               // 0.0–1.0
  evidence_r2_keys: string[];
  recommendation: string;           // max 200 chars
  compound_domains: Domain[];
  created_at: string;
}

export interface Scan {
  scan_id: string;
  unit_id: string;
  status: "queued" | "running" | "synthesizing" | "complete" | "failed";
  domain_statuses: Record<Domain, { status: string; finding_count: number }>;
  findings: Finding[];
  triggered_at: string;
  completed_at: string | null;
}

export interface CoverageMap {
  facility_id: string;
  covered_areas: Array<{ area_id: string; source: string; image_count: number }>;
  gap_areas: Array<{ area_id: string; description: string }>;
}
```

---

## 10. Agent Prompting Strategy

### 10.1 Four-Part System Prompt Structure (All Agents)

Every agent system prompt follows this structure:

1. **ROLE** — Precise domain-expert identity (e.g., "Board-Certified Infection Control Practitioner, 15 years acute care, specializing in CDC/APIC HAI prevention guidelines")
2. **CONTEXT** — Unit type, hospital context, and scenario (e.g., "You are auditing a 24-bed Medical-Surgical unit in the context of an active MRSA transmission risk scenario")
3. **TASK** — Numbered, bounded analysis tasks corresponding exactly to the sub-agents in that team
4. **OUTPUT FORMAT** — Strict JSON array schema with required fields; no preamble; no markdown

### 10.2 Label Quality Standard

**Test:** If a clinical professional read this label in the 3D model right now, would they know exactly what to check and why it matters?

Requirements:
- Names the **specific equipment or spatial condition**
- Names its **location** (room ID or corridor segment)
- Names the **risk it creates**
- Maximum **120 characters**
- Plain **clinical English** — no scores, no codes

```
GOOD: "No hand hygiene dispenser within 3 ft of Room 412 entry — MRSA contact precaution risk"
GOOD: "Crash cart in NW corridor unreachable to Rooms 308–314 within 60 sec — defibrillation delay"
GOOD: "ADC in Med Room 2 faces active walkway — 4–6 interruptions/hr at peak shift doubles error risk"

BAD: "HAI risk score: 0.87 in zone C4"
BAD: "Emergency response coverage gap detected"
BAD: "Patient safety issue in Room 207"
```

### 10.3 Recommendation Standard

- Maximum **200 characters**
- Must reference the specific guideline being violated: CDC, APIC, TJC, ANSI, ACEP
- Must state the specific remediation action

```
GOOD: "Relocate hand hygiene dispenser to within 3 ft of Room 412 entry threshold per CDC Hand Hygiene Guideline 2002 §IV.C"
GOOD: "Move crash cart from NW corridor to position covering Rooms 308–314 per AHA ACLS Cart Placement Guidelines"
```

---

## 11. Environment Variables

```bash
# .env.example

# InterSystems IRIS
IRIS_HOST=localhost
IRIS_PORT=1972
IRIS_NAMESPACE=MEDSENT
IRIS_USER=medsent_app
IRIS_PASSWORD=<set in secrets manager>
IRIS_FHIR_BASE=http://localhost:52773/fhir/r4
IRIS_HEALTH_CONNECT_ENDPOINT=https://<health-connect-cloud-id>.intersystems.io

# Google APIs
GOOGLE_API_KEY=<Maps Platform key with Street View + Places enabled>
GOOGLE_GEOCODING_API_KEY=<optional separate key>

# World Labs
WORLD_LABS_API_KEY=<world labs api key>

# Anthropic
ANTHROPIC_API_KEY=<anthropic api key>

# OpenAI (CSE synthesis pass)
OPENAI_API_KEY=<openai api key>

# Modal
MODAL_TOKEN_ID=<modal token id>
MODAL_TOKEN_SECRET=<modal token secret>

# Redis (Upstash)
REDIS_URL=rediss://<upstash-url>:6380
REDIS_PASSWORD=<upstash password>

# Cloudflare R2
R2_ACCOUNT_ID=<cloudflare account id>
R2_ACCESS_KEY_ID=<r2 access key>
R2_SECRET_ACCESS_KEY=<r2 secret key>
R2_BUCKET_NAME=medsent-assets
R2_PUBLIC_URL=https://<bucket>.r2.dev

# Next.js
NEXT_PUBLIC_MAPBOX_TOKEN=<mapbox public token>
NEXT_PUBLIC_WS_URL=wss://<backend-domain>
NEXT_PUBLIC_API_URL=https://<backend-domain>

# Auth (e.g., Clerk or Auth.js)
AUTH_SECRET=<auth secret>
AUTH_GOOGLE_ID=<google oauth client id>
AUTH_GOOGLE_SECRET=<google oauth client secret>
```

---

## 12. Project File Structure

```
medsent/
├── backend/
│   ├── main.py                         # FastAPI app, route registration
│   ├── config.py                       # Settings from environment variables
│   ├── api/
│   │   ├── facilities.py               # /api/facilities routes
│   │   ├── models.py                   # /api/models routes
│   │   ├── scans.py                    # /api/scans routes
│   │   ├── upload.py                   # /api/upload (tus) routes
│   │   ├── fhir.py                     # /api/fhir proxy routes
│   │   ├── reports.py                  # /api/reports routes
│   │   └── websocket.py                # /ws/scans WebSocket endpoint
│   ├── db/
│   │   ├── iris_client.py              # IRIS Python SDK wrapper
│   │   └── redis_client.py             # Redis pub/sub wrapper
│   ├── pipeline/
│   │   ├── image_acquisition.py        # Street View + Places + OSM fetchers
│   │   ├── classify.py                 # Claude Vision image classification
│   │   ├── scene_graph.py              # Scene graph extraction
│   │   └── world_model.py              # World Labs API integration
│   ├── agents/
│   │   ├── orchestrator.py             # Parallel Modal invocation + job management
│   │   ├── consensus.py                # Consensus Synthesis Engine
│   │   ├── ica_team.py                 # Infection Control Agent Team (Modal function)
│   │   ├── msa_team.py                 # Medication Safety Agent Team
│   │   ├── fra_team.py                 # Fall Risk Agent Team
│   │   ├── era_team.py                 # Emergency Response Agent Team
│   │   ├── pfa_team.py                 # Patient Flow Agent Team
│   │   ├── sca_team.py                 # Staff Communication Agent Team
│   │   └── prompts/
│   │       ├── ica.py                  # ICA system prompt + output schema
│   │       ├── msa.py
│   │       ├── fra.py
│   │       ├── era.py
│   │       ├── pfa.py
│   │       └── sca.py
│   ├── reports/
│   │   ├── pdf_generator.py            # PDF report generation (reportlab)
│   │   └── fhir_projector.py           # findings → FHIR DiagnosticReport/Observation
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx                    # Landing / auth redirect
│   │   ├── dashboard/
│   │   │   └── page.tsx                # Facility map overview
│   │   ├── facility/
│   │   │   ├── new/page.tsx            # Facility onboarding (map search + auto-acquire)
│   │   │   └── [id]/
│   │   │       ├── page.tsx            # Facility detail
│   │   │       ├── coverage/page.tsx   # Coverage map + supplemental upload
│   │   │       ├── model/[uid]/page.tsx# World model viewer
│   │   │       └── report/[uid]/page.tsx
│   ├── components/
│   │   ├── viewer/
│   │   │   ├── SplatRenderer.tsx       # React Three Fiber + SparkJS
│   │   │   ├── AnnotationOverlay.tsx   # 3D billboard system
│   │   │   ├── FindingBillboard.tsx    # Single annotated label in 3D space
│   │   │   └── CameraController.tsx   # Fly-to + WASD navigation
│   │   ├── findings/
│   │   │   ├── FindingFeed.tsx         # Right panel with finding cards
│   │   │   ├── FindingCard.tsx
│   │   │   ├── DomainFilterBar.tsx
│   │   │   └── AgentActivityRibbon.tsx # Live scan progress + WebSocket feed
│   │   ├── facility/
│   │   │   ├── FacilityMap.tsx         # Mapbox map with facility markers
│   │   │   ├── CoverageMap.tsx         # Green/amber coverage overlay
│   │   │   └── SupplementalUpload.tsx  # tus upload dropzone for gap fills
│   │   └── ui/                         # Shared design system components
│   ├── hooks/
│   │   ├── useScanStream.ts            # WebSocket → Zustand findings store
│   │   ├── useSplatModel.ts            # World model loading + streaming
│   │   └── useCoverageMap.ts           # Coverage map data fetching
│   ├── store/
│   │   └── index.ts                    # Zustand store (findings, filters, camera state)
│   ├── lib/
│   │   ├── constants.ts                # Domain colors, severity sizes
│   │   └── api.ts                      # Typed API client (generated from OpenAPI)
│   └── types/
│       └── index.ts                    # Shared TypeScript types
├── iris/
│   ├── iris.cpf                        # IRIS configuration file
│   ├── init.sh                         # IRIS first-run initialization script
│   │                                   # (creates namespace, RBAC roles, Secure Wallet, FHIR server)
│   └── fhir_config.json                # FHIR server configuration
├── docker-compose.yml                  # IRIS + FastAPI + Redis (local dev)
├── docker-compose.prod.yml             # Production override (iris-lockeddown image)
└── PRD.md                              # This file
```

---

## 13. Implementation Roadmap

### Phase 1 — Foundation: World Model Pipeline End-to-End

**Exit criterion:** A completed, navigable 3D world model generated from public imagery for a real hospital facility, viewable in-browser with scene graph attached.

- Scaffold Next.js frontend + FastAPI backend
- Set up IRIS for Health container (`iris-lockeddown`). Initialize IRIS globals schema, Secure Wallet, RBAC roles (SafetyOfficer, UnitManager, Auditor), and FHIR server via `iris/init.sh`
- Set up Cloudflare R2, Redis (Upstash), Modal workspace
- Implement Google Street View + Places API image acquisition pipeline
- Implement Claude Vision image classification (11 categories) and scene graph extraction
- Integrate World Labs API. Test with a real, publicly photographed hospital (e.g., a large academic medical center with Street View Indoor coverage)
- Implement React Three Fiber + SparkJS splat viewer — stream `.splat` binary from R2
- Build Mapbox facility selector with auto-geocoding and coverage map overlay
- Build supplemental upload UI (React Dropzone + tus, gap-fill only)
- End-to-end integration test: facility search → image acquisition → classification → scene graph → world model generation → viewer

### Phase 2 — Agent Teams and Live Annotation

**Exit criterion:** All six agent teams producing findings on a completed world model, streamed live to the 3D annotation overlay via WebSocket.

- Implement ICA and ERA agent teams first (highest clinical urgency) — Modal functions with Redis streaming
- Verify all findings written to IRIS before Redis publish
- Implement WebSocket server (`/ws/scans/{unit_id}/live`) and connect to frontend `useScanStream` hook
- Build 3D annotation overlay (colored billboard system) and Finding Feed panel
- Implement MSA and FRA agent teams
- Implement PFA and SCA agent teams
- Implement Consensus Synthesis Engine (compound severity, CRITICAL promotion)
- Project all findings as FHIR DiagnosticReport resources in IRIS FHIR repository
- Implement IRIS IntegratedML unit risk trend model

### Phase 3 — Output, Security Hardening, and Pilot

**Exit criterion:** Production-ready system with 3 completed pilot scans reviewed by a clinical expert, IRIS HIPAA controls audited, and full report export working.

- Conduct 3 pilot scans on real hospital facilities. Clinical expert reviews agent findings vs. ground truth.
- Tune agent prompts based on pilot results — target 80%+ clinical expert agreement on HIGH/CRITICAL findings
- Build PDF report export (reportlab) and `findings_manifest.json` download
- Implement FHIR DiagnosticReport push to sandbox Epic/Cerner via IRIS Health Connect Cloud
- IRIS security audit: Secure Wallet key management, RBAC role enforcement, audit log completeness, TLS verification
- Production deployment: IRIS on dedicated node (private VPC), FastAPI on Fly.io, R2 egress hardening
- Implement multi-tenant org support (org-scoped IRIS RBAC), auth (Clerk or Auth.js)
- Documentation and v1.0 release

---

## 14. Key Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Public imagery insufficient for interior clinical spaces | HIGH | Street View Indoor + Places Photos covers lobbies, ED entries, main corridors. Coverage map guides users to upload only targeted gap-fill images (5–15 photos), not hundreds. Confidence is discounted for inferred vs. directly-imaged spaces in CSE. |
| World model fidelity low for unimaged zones | MEDIUM | Scene graph inferred from OSM topology + architectural norm priors for unimaged zones. Agent labels explicitly state evidence basis ("inferred from floor plan" vs. "observed in Street View image"). |
| Agent findings contain hallucinations | HIGH | Multi-agent consensus reduces single-agent error substantially. Confidence threshold (< 0.5) suppresses low-confidence findings from display. Evidence image tile shown per finding. Clinical review recommended before acting on CRITICAL findings. |
| HIPAA compliance for facility data | CRITICAL | InterSystems IRIS Secure Wallet (AES-256 at rest), RBAC at data layer, Health Connect TLS 1.3 in transit, full audit logging — all IRIS-native. No PHI stored. IRIS security audit in Phase 3. |
| IRIS deployment complexity | MEDIUM | `intersystems-irispython` SDK well-documented. IRIS runs in Docker; `iris-lockeddown` pre-configures security. `iris/init.sh` automates first-run setup. InterSystems provides 24/7 production support. |
| Google API cost at scale | LOW | ~$0.21/facility for full exterior acquisition. Images cached in R2 indefinitely (annual refresh). Even 1,000 facilities = ~$210 total acquisition cost. |

---

*MedSentinel PRD v1.1 — For Engineering Implementation*
