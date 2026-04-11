# Frontend

## Stack Contract

- Next.js 15 App Router
- React 19
- Zustand for viewer state
- Mapbox-ready facility overview shell
- React Three Fiber-ready viewer surface

## Route Contract

- `/`
- `/dashboard`
- `/facility/new`
- `/facility/[id]`
- `/facility/[id]/coverage`
- `/facility/[id]/model/[uid]`
- `/facility/[id]/report/[uid]`

## UI Priorities

- The model page must preserve the 70/30 viewer-to-feed relationship on desktop.
- Facility detail and model surfaces should always resolve to the newest world model available for each unit.
- Findings should remain readable at a glance with domain, severity, room, and recommendation.
- Coverage workflows must distinguish green covered zones from amber gaps.
- Agent activity should remain visible during scan execution.
- The scenario simulation page should keep the left trace feed readable while the right panel renders the canonical live reasoning graph.
- Live simulation visuals should prefer structured graph updates over raw text streams; revisits must rehydrate from persisted graph state when available.
