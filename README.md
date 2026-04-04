# MedSentinel

Implementation scaffold for the MedSentinel PRD: a hospital safety platform that auto-acquires public imagery, synthesizes a world model, deploys six agent teams, and streams spatially anchored findings into a Next.js viewer backed by FastAPI and IRIS-for-Health-aligned interfaces.

## Repository Layout

- `backend/`: FastAPI APIs, pipeline steps, agent orchestration, and report generation.
- `frontend/`: Next.js 15 App Router UI for dashboard, coverage, world model viewer, and reports.
- `iris/`: Locked-down IRIS configuration placeholders for namespace, Secure Wallet, roles, and FHIR setup.
- `docs/`: Agent-first repository knowledge base and execution-plan structure.

## Quick Start

1. Create a virtual environment and install `backend/requirements.txt`.
2. Install dependencies in `frontend/` and run `npm run build`.
3. Start the backend with `uvicorn backend.main:app --reload`.
4. Start the frontend with `npm run dev` inside `frontend/`.
