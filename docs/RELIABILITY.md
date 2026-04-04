# Reliability

## Principles

- Keep external service boundaries explicit and mockable.
- Prefer deterministic local fallbacks when cloud services are unavailable.
- Preserve typed contracts between frontend and backend.
- Publish findings after persistence succeeds.

## Current Guardrails

- In-memory IRIS and Redis replacements keep local execution deterministic.
- Consensus synthesis is unit tested.
- Health and facilities endpoints are covered by API tests.
- Signed world-model URLs and FHIR projections use stable local generation paths.

