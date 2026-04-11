# Architecture

MedSim is organized into four legible layers:

1. `frontend/`
   Next.js 15 App Router UI for facility onboarding, coverage review, world model viewing, and report export.
2. `backend/`
   FastAPI APIs, world-model pipeline stages, six domain agent teams, consensus synthesis, and export generation.
3. `iris/`
   Deployment and first-run configuration for InterSystems IRIS for Health, modeled here with dev-safe placeholders.
4. `docs/`
   Repository knowledge base for agents and humans. This is the source of truth for architecture, plans, product specs, quality, reliability, and security guidance.

## Package Boundaries

- `backend/api/`
  Transport layer only. Keep HTTP and WebSocket concerns here.
- `backend/db/`
  Persistence adapters. `iris_client.py` and `redis_client.py` define swap-friendly seams.
- `backend/pipeline/`
  Image acquisition, classification, scene-graph extraction, and world-model generation.
- `backend/agents/`
  Domain teams, prompts, consensus synthesis, and scan orchestration.
- `backend/reports/`
  PDF and FHIR projection logic.
- `frontend/components/`
  Route-independent UI building blocks grouped by viewer, findings, facility, and shared UI.
- `frontend/hooks/`
  WebSocket, model-loading, and coverage-fetching hooks.
- `frontend/store/`
  Global viewer state and interaction state.

## Development Notes

- Current persistence is in-memory for local determinism, but public interfaces mirror the PRD’s IRIS-backed behavior.
- Setting `MEDSIM_IRIS_MODE=native` switches the persistence seam to the InterSystems Native SDK and the configured FHIR repository.
- Current world-model rendering is a viewer shell with annotation overlays and signed-URL plumbing. SparkJS wiring can replace the placeholder surface without route changes.
- Current agent outputs are deterministic synthetic findings shaped to the PRD schema so downstream viewer and report flows are testable now.
