# AGENTS.md

This repository follows an agent-first workflow. Treat this file as the table of contents, not the full manual.

## Mission

Build MedSentinel: a Next.js + FastAPI platform that acquires public hospital imagery, generates a navigable world model, deploys six safety agent teams, and exports findings as PDF and FHIR artifacts.

## Working Rules

- Keep the repository as the system of record. If a decision matters, encode it in `docs/`.
- Prefer small, legible changes over hidden cleverness.
- Maintain the PRD contract in `PRD.md` unless a task explicitly changes product scope.
- Preserve the directory layout promised in the PRD.
- When implementation diverges from production integrations, keep interfaces stable and note the development fallback in docs.
- Add or update tests when behavior changes.
- Favor deterministic mockable seams for external services: Google APIs, Anthropic, World Labs, IRIS, Redis, Modal, R2.
- Never bury important operating knowledge in this file if it belongs in a narrower source of truth under `docs/`.

## Entry Points

- Product and scope: [PRD.md](/Users/kokon/work/trauma-reconstruction/PRD.md)
- Architecture map: [ARCHITECTURE.md](/Users/kokon/work/trauma-reconstruction/ARCHITECTURE.md)
- Frontend guidance: [docs/FRONTEND.md](/Users/kokon/work/trauma-reconstruction/docs/FRONTEND.md)
- Reliability expectations: [docs/RELIABILITY.md](/Users/kokon/work/trauma-reconstruction/docs/RELIABILITY.md)
- Security expectations: [docs/SECURITY.md](/Users/kokon/work/trauma-reconstruction/docs/SECURITY.md)
- Quality grading and gaps: [docs/QUALITY_SCORE.md](/Users/kokon/work/trauma-reconstruction/docs/QUALITY_SCORE.md)
- Active and completed plans: [docs/PLANS.md](/Users/kokon/work/trauma-reconstruction/docs/PLANS.md)
- Product specs index: [docs/product-specs/index.md](/Users/kokon/work/trauma-reconstruction/docs/product-specs/index.md)
- Design docs index: [docs/design-docs/index.md](/Users/kokon/work/trauma-reconstruction/docs/design-docs/index.md)

## Implementation Map

- `backend/`
  FastAPI routes, orchestration, synthetic IRIS/Redis adapters, pipeline stages, and report generators.
- `frontend/`
  Next.js App Router pages, viewer shell, facility flows, Zustand state, and typed API access.
- `iris/`
  Locked-down IRIS deployment placeholders and first-run configuration stubs.
- `tests/`
  Backend verification for consensus behavior and API health.

## Expected Workflow

1. Read the relevant spec and docs before editing.
2. Update the nearest source-of-truth document if behavior or architecture changes.
3. Implement the code.
4. Run the narrowest useful verification first, then broader checks.
5. Record any remaining gaps in the appropriate plan or quality doc.

## Where To Put New Knowledge

- New architectural decisions: `ARCHITECTURE.md` or `docs/design-docs/`
- Product behavior and UX contracts: `docs/product-specs/`
- Execution status, phased work, and debt: `docs/exec-plans/`
- Generated inventories or schemas: `docs/generated/`
- External references and condensed agent aids: `docs/references/`

## Current Reality

- External integrations are scaffolded behind stable interfaces with development-safe synthetic behavior.
- The frontend implements the PRD route structure and main viewer/facility/report surfaces.
- The backend exposes the PRD API surface and uses in-memory IRIS-style storage for local execution.
- The docs tree is intentionally structured for progressive disclosure, based on OpenAI’s harness engineering recommendation that `AGENTS.md` stay short while `docs/` acts as the system of record.
- Source reference for the docs layout philosophy: [OpenAI harness engineering article](https://openai.com/index/harness-engineering/).
