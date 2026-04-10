# CLAUDE.md

This file is the agent entry point for the MedSentinel repository. Read it before touching any code.

## Mission

Build MedSentinel: a Next.js 15 + FastAPI platform that acquires public hospital imagery, generates a Gaussian-splat navigable 3D world model via World Labs, deploys six safety agent teams (Anthropic Claude), and exports findings as PDF and FHIR R4 artifacts — all secured through InterSystems IRIS for Health.

For full product scope see `PRD.md`. For architecture decisions see `ARCHITECTURE.md`. For agent team details see `AGENTS.md`.

---

## Repository Map

```
backend/api/          HTTP + WebSocket transport only — no business logic here
backend/agents/       Six domain teams, consensus synthesis, orchestrator
backend/db/           Persistence adapters — iris_client, redis_client, r2_client
backend/pipeline/     Image acquisition → classify → scene graph → world model
backend/reports/      PDF (ReportLab) and FHIR DiagnosticReport generation
backend/config.py     Pydantic Settings — all env vars loaded here
backend/models.py     Shared Pydantic data models (Finding, Scan, Facility, etc.)
frontend/app/         Next.js App Router pages
frontend/components/  UI components: viewer/, findings/, facility/, shared/
frontend/hooks/       WebSocket, model-loading, coverage hooks
frontend/store/       Zustand global state
iris/                 IRIS CPF config, FHIR config JSON, first-run init.sh
docs/                 Source of truth for architecture, plans, quality, security
tests/                Backend pytest suite (uses in-memory stubs, no live API keys)
```

---

## Working Rules

- **Read before editing.** Check the relevant spec in `docs/` before changing behavior.
- **Keep interfaces stable.** External services (IRIS, Redis, World Labs, Modal, R2, Google) are wired behind swap-friendly seams in `backend/db/` and `backend/pipeline/`. Do not scatter direct API calls into business logic.
- **Synthetic fallbacks.** `MEDSENTINEL_USE_SYNTHETIC_FALLBACKS=true` bypasses all live external API calls. Tests rely on this — never break it.
- **Small, legible changes.** Prefer narrow, targeted edits over sweeping refactors.
- **Update docs when behavior changes.** If a decision matters, encode it in `docs/` or `ARCHITECTURE.md`.
- **Add or update tests when behavior changes.** The test suite is in `tests/`; run with `pytest`.
- **Never store secrets in code.** All credentials come from `backend/config.py` via `pydantic-settings` and `.env`.
- **IRIS ports are internal-only.** Ports `1972` and `52773` must never be exposed to the public internet.

---

## Development Setup (Quick Reference)

```bash
# 1. Infrastructure
docker compose up iris redis -d

# 2. Python backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env   # fill in keys, or set MEDSENTINEL_USE_SYNTHETIC_FALLBACKS=true

# 3. Start backend (uvicorn, port 8000, hot-reload)
./scripts/start-backend.sh

# 4. Frontend
cd frontend && npm install && npm run dev   # port 3000

# 5. Tests
pytest
```

---

## Key Data Models (`backend/models.py`)

- `Facility` — hospital record with location, Google place ID, world model reference
- `Scan` — one full scan run: six `DomainStatus` entries + list of `Finding`
- `Finding` — single spatially anchored risk finding: `scan_id`, `domain`, `room_id`, `severity`, `description`, `recommendation`
- `DomainStatus` — per-domain run status and finding count for a scan

---

## Agent Architecture

Six domain teams run concurrently in `agents/orchestrator.py` via `asyncio.gather`. Each team module exposes a single `async def run(scan_id, world_model_dict) -> list[dict]` function.

| Team | File | Domain |
|---|---|---|
| ICA | `agents/ica_team.py` | Infection Control |
| MSA | `agents/msa_team.py` | Medication Safety |
| FRA | `agents/fra_team.py` | Fall Risk |
| ERA | `agents/era_team.py` | Emergency Response |
| PFA | `agents/pfa_team.py` | Patient Flow |
| SCA | `agents/sca_team.py` | Staff Communication |

After gather, `agents/consensus.py` runs the Consensus Synthesis Engine (CSE) — a cross-domain OpenAI pass that deduplicates and re-ranks findings. The orchestrator then persists the final list to IRIS and publishes each finding to Redis for real-time streaming.

---

## Persistence Layer

All reads and writes go through adapters, never direct SDK calls in business logic:

- `db/iris_client.py` — IRIS for Health via `intersystems-irispython`. Handles facilities, world models, scans, findings, and FHIR projection.
- `db/redis_client.py` — Redis pub/sub for real-time scan events. Channels follow `scan:<unit_id>`.
- `db/r2_client.py` — Cloudflare R2 for `.spz` world model asset storage and signed-URL generation.

In local dev and tests, `iris_client` falls back to in-memory dicts when IRIS is unreachable. `redis_client` does the same for Redis. This behavior is controlled by `MEDSENTINEL_USE_SYNTHETIC_FALLBACKS`.

---

## World Model Pipeline (`backend/pipeline/`)

1. `facility_lookup.py` — Google Geocoding + Places API → facility metadata
2. `image_acquisition.py` — Google Street View panoramas + Places Photos → list of `{public_url, source, heading}`
3. `classify.py` — Claude Vision classifies each image → room type tags, hazard signals
4. `scene_graph.py` — builds structured JSON scene graph from classifications
5. `world_model.py` — submits to World Labs Marble API, polls for completion, downloads `.spz`, uploads to R2

---

## API Surface (`backend/api/`)

| Module | Routes |
|---|---|
| `facilities.py` | `GET/POST /api/facilities`, `GET /api/facilities/{id}` |
| `scans.py` | `POST /api/scans`, `GET /api/scans/{id}` |
| `reports.py` | `GET /api/scans/{id}/report.pdf`, `GET /api/scans/{id}/report.fhir` |
| `fhir.py` | FHIR R4 proxy to IRIS FHIR endpoint |
| `upload.py` | Resumable image upload via tus protocol → R2 |
| `websocket.py` | `WS /ws/scan/{unit_id}` — streams findings from Redis pub/sub |

---

## Frontend Architecture

- **App Router** (`frontend/app/`) — route structure matches PRD: `/`, `/facilities/[id]`, `/scan/[id]`, `/scan/[id]/report`
- **Viewer** — React Three Fiber + `@mkkellogg/gaussian-splats-3d` renders the `.spz` world model; findings are overlaid as 3D annotation markers
- **State** — Zustand stores in `frontend/store/` manage viewer camera state and selected findings
- **Real-time** — `hooks/useWebSocket.ts` connects to `WS /ws/scan/{unit_id}` and appends incoming findings to store
- **Map** — Mapbox GL renders the facility selection map; `NEXT_PUBLIC_MAPBOX_TOKEN` must be set

---

## Where to Put New Work

| Type of change | Location |
|---|---|
| New architectural decision | `ARCHITECTURE.md` or `docs/design-docs/` |
| Product behavior / UX contract | `docs/product-specs/` |
| Execution status / phased work / debt | `docs/exec-plans/` |
| New agent domain | `backend/agents/` — new `<abbr>_team.py`, register in `orchestrator.py` DOMAINS tuple |
| New pipeline stage | `backend/pipeline/` — keep stages independent and mockable |
| New API route | `backend/api/` — transport concerns only; call into pipeline or db adapters |
| New frontend page | `frontend/app/` using App Router conventions |
| New shared component | `frontend/components/shared/` |

---

## Current Reality (Development State)

- All external integrations (IRIS, World Labs, Google, Modal) are scaffolded behind stable interfaces with deterministic synthetic fallback behavior when `MEDSENTINEL_USE_SYNTHETIC_FALLBACKS=true`.
- The frontend implements the full PRD route structure and main viewer/facility/report surfaces.
- The backend exposes the full PRD API surface using in-memory IRIS-style storage for local execution.
- Agent outputs are deterministic synthetic findings shaped to the PRD schema — downstream viewer and report flows are testable without live API keys.
- SparkJS / World Labs viewer integration is a viewer shell awaiting live `.spz` asset wiring in production.
