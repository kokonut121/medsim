# MedSim

> AI World Model + Agent Orchestration Network for Hospital Safety & Operations Intelligence

Built for **Harvard's HSIL Hackathon**. MedSim automatically acquires public imagery of any hospital, generates a navigable 3D Gaussian-splat world model, then deploys six specialized AI agent teams into that model to identify and spatially annotate critical safety risks. Findings stream in real time to a Next.js viewer and are exportable as PDF and FHIR R4 DiagnosticReport artifacts, all secured through InterSystems IRIS for Health.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Repository Layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Local Development](#local-development)
- [Docker Deployment](#docker-deployment)
- [Production Deployment](#production-deployment)
- [Running Tests](#running-tests)
- [Six Safety Domains](#six-safety-domains)
- [Data Flow](#data-flow)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 0: InterSystems IRIS for Health                          │
│  (Secure Wallet · FHIR R4 · RBAC · Audit Log · IntegratedML)    │
├──────────────┬──────────────────────────┬───────────────────────┤
│  Layer 1     │  Layer 2                 │  Layer 3              │
│  Image       │  World Model Pipeline    │  Agent Orchestration  │
│  Acquisition │  Claude Vision →         │  6 Domain Teams       │
│  ────────    │  Scene Graph →           │  Modal (A10G GPUs)    │
│  Street View │  World Labs API →        │  Redis Pub/Sub        │
│  Places API  │  .spz / .splat binary    │  CSE Synthesis        │
│  OSM         │  → Cloudflare R2         │                       │
├──────────────┴──────────────────────────┴───────────────────────┤
│  Layer 4: Frontend                                              │
│  Next.js 15 · Mapbox · React Three Fiber · Gaussian Splats 3D   │
│  Zustand · WebSockets · Recharts                                │
└─────────────────────────────────────────────────────────────────┘
```

The system has four clearly separated concerns:

1. **IRIS for Health** — all persistent storage, encryption (Secure Wallet AES-256), FHIR R4 repository, RBAC, and audit logging. FastAPI never touches raw disk; it calls IRIS via the `intersystems-irispython` SDK.
2. **Image Acquisition + World Model Pipeline** — `backend/pipeline/` pulls imagery from Google Street View / Places, classifies it with Claude Vision, builds a scene graph, submits to the World Labs Marble API to generate a Gaussian-splat world model, and stores the `.spz` asset in Cloudflare R2.
3. **Agent Orchestration** — `backend/agents/` runs six domain teams in parallel using `asyncio.gather`. Each team calls Anthropic Claude with domain-specific prompts against the world model data. Raw results are merged by the Consensus Synthesis Engine (CSE), which uses OpenAI for a final cross-domain pass. Findings are persisted to IRIS and published to Redis channels for real-time streaming.
4. **Frontend** — Next.js 15 App Router renders the facility map (Mapbox), 3D world model viewer (React Three Fiber + `@mkkellogg/gaussian-splats-3d`), live findings panel (WebSocket), and PDF/FHIR export.

---

## Tech Stack

### Backend (Python)

| Library | Version | Purpose |
|---|---|---|
| `fastapi` | 0.115.12 | HTTP and WebSocket API server |
| `uvicorn` | 0.34.0 | ASGI server |
| `pydantic` / `pydantic-settings` | 2.11.3 / 2.8.1 | Data validation and settings management |
| `httpx` | 0.28.1 | Async HTTP client — Google APIs, World Labs, Anthropic |
| `redis` | 5.2.1 | Pub/sub for real-time finding events (Upstash in production) |
| `reportlab` | 4.3.1 | PDF report generation |
| `pytest` | 8.3.5 | Test runner |
| `intersystems-irispython` | latest | IRIS for Health SDK — globals, FHIR, Secure Wallet |
| `anthropic` | latest | Claude Vision API for image classification and agent teams |
| `modal` | latest | Serverless GPU (A10G) hosting for agent inference |

### Frontend (TypeScript)

| Library | Version | Purpose |
|---|---|---|
| `next` | 15.5.14 | React framework, App Router, server components |
| `react` | 19.0.0 | UI rendering |
| `@react-three/fiber` | 9.1.0 | React renderer for Three.js — 3D world model viewer |
| `@react-three/drei` | 10.0.4 | Three.js helpers (camera controls, loaders) |
| `@mkkellogg/gaussian-splats-3d` | 0.4.7 | Gaussian splat renderer for `.spz` / `.ksplat` world models |
| `three` | 0.174.0 | Underlying 3D engine |
| `mapbox-gl` | 3.11.0 | Facility selection map |
| `zustand` | 5.0.3 | Global viewer and interaction state |
| `recharts` | 2.15.1 | Risk score and coverage charts |
| `react-dropzone` | 14.3.8 | Supplemental image upload |
| `tus-js-client` | 4.2.3 | Resumable uploads to R2 |

### External Services

| Service | Purpose |
|---|---|
| **InterSystems IRIS for Health** | Primary datastore, FHIR R4, encryption, RBAC |
| **Google Street View / Places API** | Public imagery acquisition |
| **World Labs Marble API** | Gaussian-splat 3D world model generation |
| **Anthropic Claude** | Vision classification, six agent domain teams |
| **OpenAI** | Consensus Synthesis Engine cross-domain pass |
| **Modal** | Serverless A10G GPU hosting for agent inference |
| **Redis / Upstash** | Real-time pub/sub for scan findings |
| **Cloudflare R2** | `.spz` world model asset storage |
| **Mapbox** | Facility map tiles and geocoding |

---

## Repository Layout

```
trauma-reconstruction/
├── backend/
│   ├── api/           # FastAPI route modules (facilities, scans, reports, FHIR, WebSocket)
│   ├── agents/        # Six domain agent teams + consensus synthesis + orchestrator
│   │   ├── ica_team.py        # Infection Control
│   │   ├── msa_team.py        # Medication Safety
│   │   ├── fra_team.py        # Fall Risk
│   │   ├── era_team.py        # Emergency Response
│   │   ├── pfa_team.py        # Patient Flow
│   │   ├── sca_team.py        # Staff Communication
│   │   ├── consensus.py       # CSE — cross-domain synthesis
│   │   └── orchestrator.py    # asyncio.gather across all six teams
│   ├── db/            # Persistence adapters (iris_client, redis_client, r2_client)
│   ├── pipeline/      # Image acquisition → classify → scene graph → world model
│   ├── reports/       # PDF and FHIR DiagnosticReport export
│   ├── config.py      # Pydantic Settings (reads .env)
│   ├── models.py      # Shared Pydantic data models
│   ├── main.py        # FastAPI app factory
│   └── requirements.txt
├── frontend/
│   ├── app/           # Next.js App Router pages
│   ├── components/    # UI components grouped by viewer / findings / facility / shared
│   ├── hooks/         # WebSocket, model-loading, coverage-fetching hooks
│   ├── store/         # Zustand global state
│   ├── lib/           # API client utilities
│   └── types/         # Shared TypeScript types
├── iris/              # IRIS deployment config (CPF file, FHIR config, init script)
├── docs/              # Architecture, design docs, product specs, reliability, security
├── scripts/
│   └── start-backend.sh
├── tests/             # Backend pytest suite
├── docker-compose.yml         # Local dev (iris + backend + redis)
├── docker-compose.prod.yml    # Production overrides
├── pytest.ini
└── .env.example
```

---

## Prerequisites

- **Python 3.11+**
- **Node.js 20+**
- **Docker + Docker Compose** (required for IRIS; optional for full-stack local)
- **InterSystems IRIS for Health** image access — either pull from the [InterSystems Container Registry](https://containers.intersystems.com) or use the community image path described in `./scripts/bootstrap-iris.sh`.
- API keys for: Google Maps Platform, World Labs, Anthropic, OpenAI, Modal, Cloudflare R2, Mapbox (see [Environment Variables](#environment-variables))

---

## Environment Variables

Copy `.env.example` to `.env` and fill in all values before starting any service.

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `IRIS_HOST` | Yes | IRIS hostname (default: `localhost`) |
| `IRIS_PORT` | Yes | IRIS SuperServer port (default: `1972`) |
| `IRIS_NAMESPACE` | Yes | IRIS namespace (`MEDSENT`) |
| `IRIS_USER` | Yes | IRIS application user |
| `IRIS_PASSWORD` | Yes | IRIS application user password |
| `IRIS_FHIR_BASE` | Yes | IRIS FHIR R4 base URL |
| `IRIS_HEALTH_CONNECT_ENDPOINT` | No | Health Connect Cloud endpoint for EHR push |
| `GOOGLE_API_KEY` | Yes | Maps Platform key with Street View + Places enabled |
| `WORLD_LABS_API_KEY` | Yes | World Labs Marble API key |
| `ANTHROPIC_API_KEY` | Yes | Anthropic Claude API key |
| `OPENAI_API_KEY` | Yes | OpenAI key for CSE synthesis pass |
| `MODAL_TOKEN_ID` | No | Modal token ID (required for GPU agent hosting) |
| `MODAL_TOKEN_SECRET` | No | Modal token secret |
| `REDIS_URL` | Yes | Redis connection URL (Upstash `rediss://` in prod) |
| `REDIS_PASSWORD` | No | Redis password |
| `R2_ACCOUNT_ID` | Yes | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | Yes | R2 access key |
| `R2_SECRET_ACCESS_KEY` | Yes | R2 secret key |
| `R2_BUCKET_NAME` | Yes | R2 bucket name (e.g. `medsent-assets`) |
| `R2_PUBLIC_URL` | Yes | Public R2 bucket URL |
| `NEXT_PUBLIC_MAPBOX_TOKEN` | Yes | Mapbox public token |
| `NEXT_PUBLIC_WS_URL` | Yes | WebSocket URL (e.g. `ws://127.0.0.1:8000`) |
| `NEXT_PUBLIC_API_URL` | Yes | Backend API base URL |
| `AUTH_SECRET` | Yes | Auth.js / Clerk secret |
| `AUTH_GOOGLE_ID` | Yes | Google OAuth client ID |
| `AUTH_GOOGLE_SECRET` | Yes | Google OAuth client secret |
| `MEDSENTINEL_USE_SYNTHETIC_FALLBACKS` | No | Set `true` to run locally without live API keys |

> **Synthetic fallbacks**: setting `MEDSENTINEL_USE_SYNTHETIC_FALLBACKS=true` skips all external API calls (World Labs, Google, Modal) and returns deterministic stub data. This lets you run and develop the full stack with only Redis and IRIS running.

---

## Local Development

### 1. Start infrastructure (IRIS + Redis)

```bash
docker compose up iris redis -d
```

Wait ~30 seconds for IRIS to initialize. The first-run script at `iris/init.sh` creates the `MEDSENT` namespace, Secure Wallet, and FHIR endpoint.

If you need the alternative bootstrap flow, run `./scripts/bootstrap-iris.sh`. Local development can use `intersystems/irishealth-community:latest-cd`; production can override `IRIS_IMAGE` and attach a properly permissioned durable data mount.

### 2. Set up the Python backend

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your API keys
# For a no-key local run: set MEDSENTINEL_USE_SYNTHETIC_FALLBACKS=true
```

### 4. Start the backend

```bash
./scripts/start-backend.sh
# FastAPI available at http://127.0.0.1:8000
# Interactive docs at http://127.0.0.1:8000/docs
```

### 5. Install and start the frontend

```bash
cd frontend
npm install
npm run dev
# Next.js available at http://localhost:3000
```

---

## Docker Deployment

The `docker-compose.yml` runs all three services (IRIS, backend, Redis) on an internal bridge network. The backend is the only service that exposes a public port.

```bash
# Build and start all services
docker compose up --build

# Tail logs
docker compose logs -f backend

# Stop
docker compose down
```

> **Security:** IRIS ports `1972` and `52773` are on the `internal` network only. Never expose them publicly. FastAPI connects to IRIS over the internal network via `intersystems-irispython`.

---

## Production Deployment

### Prerequisites

- A server or cloud VM with Docker and Docker Compose v2
- Domain with TLS termination (nginx or Caddy in front of port 8000)
- Managed Redis (Upstash recommended — use `rediss://` URL)
- Cloudflare R2 bucket created and public URL configured
- IRIS SuperServer not exposed to the public internet

### Steps

1. **Clone and configure**

   ```bash
   git clone https://github.com/kokonut121/trauma-reconstruction.git
   cd trauma-reconstruction
   cp .env.example .env
   # Fill in all production values in .env
   ```

2. **Build and start with production overrides**

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
   ```

   The `docker-compose.prod.yml` sets `MEDSENTINEL_ENV=production`, removes IRIS public port bindings, and adds `restart: unless-stopped`.

3. **Verify IRIS initialization**

   ```bash
   docker compose logs iris | grep "IRIS startup complete"
   ```

4. **Build and deploy the frontend**

   The frontend is a separate Next.js app. Deploy to Vercel, Cloudflare Pages, or any Node host:

   ```bash
   cd frontend
   npm install
   npm run build
   npm run start          # or deploy the .next output to your host
   ```

   Set all `NEXT_PUBLIC_*` environment variables in your hosting platform's dashboard.

5. **Set up TLS reverse proxy**

   Point your reverse proxy to `http://backend:8000`. Example nginx block:

   ```nginx
   location / {
       proxy_pass http://127.0.0.1:8000;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection "upgrade";   # required for WebSocket
       proxy_set_header Host $host;
   }
   ```

6. **Configure IRIS FHIR endpoint**

   After IRIS is running, verify the FHIR R4 endpoint:

   ```bash
   curl http://localhost:52773/fhir/r4/metadata
   ```

   Then set `IRIS_FHIR_BASE` in `.env` to the internal Docker hostname: `http://iris:52773/fhir/r4`.

---

## Running Tests

```bash
# Activate virtualenv first
source .venv/bin/activate

# Run all backend tests
pytest

# Run a specific test file
pytest tests/test_consensus.py -v

# Run with coverage
pytest --cov=backend
```

Tests use in-memory IRIS/Redis stubs and do not require external API keys.

---

## Six Safety Domains

Each agent team ingests the facility's world model data and produces spatially anchored `Finding` records ranked by severity.

| Team | Module | Problem Domain | Key Spatial Signals |
|---|---|---|---|
| **ICA** | `agents/ica_team.py` | Hospital-Acquired Infections | Hand sanitizer placement, isolation proximity, clean/dirty traffic paths |
| **MSA** | `agents/msa_team.py` | Medication Errors | ADC placement, prep area lighting, handoff workstation access |
| **FRA** | `agents/fra_team.py` | Patient Falls | Bedside clearance, call light position, nursing station sightlines |
| **ERA** | `agents/era_team.py` | Code Blue Response | Crash cart coverage radius, AED accessibility, corridor obstructions |
| **PFA** | `agents/pfa_team.py` | ED Overcrowding / Boarding | Bed topology, transfer pathway distance, discharge routing |
| **SCA** | `agents/sca_team.py` | Staff Communication Failure | Handoff zone infrastructure, walking distances, quiet zone presence |

All six run concurrently via `asyncio.gather` in `agents/orchestrator.py`. The **Consensus Synthesis Engine** (`agents/consensus.py`) deduplicates overlapping findings and ranks the final list cross-domain.

---

## Data Flow

```
User selects facility on Mapbox map
    ↓
POST /api/facilities  →  Google Geocoding + Places lookup
    ↓
pipeline/image_acquisition.py  →  Street View + Places Photos
    ↓
pipeline/classify.py  →  Claude Vision: tag room types, hazard signals
    ↓
pipeline/scene_graph.py  →  structured scene graph JSON
    ↓
pipeline/world_model.py  →  World Labs Marble API  →  .spz asset → R2
    ↓
POST /api/scans  →  agents/orchestrator.py
    ↓
asyncio.gather(ica, msa, fra, era, pfa, sca)  [Modal A10G GPUs]
    ↓
agents/consensus.py  →  CSE synthesis (OpenAI cross-domain pass)
    ↓
iris_client.write_findings()  →  IRIS Secure Wallet storage
    ↓
redis_client.publish()  →  WebSocket → browser live findings panel
    ↓
/api/reports  →  PDF (ReportLab) or FHIR DiagnosticReport (IRIS FHIR R4)
```
