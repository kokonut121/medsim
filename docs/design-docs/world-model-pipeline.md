# World Model Pipeline

The pipeline follows the PRD sequence:

1. Geocode and identify the Google Place record.
2. Acquire Street View, Places photo, and OSM topology inputs.
3. Classify images into 11 semantic buckets.
4. Extract a scene graph.
5. Generate the world model.
6. Store references for viewer and scan execution.

Current implementation uses deterministic synthetic fallbacks for acquisition, classification, and world generation so downstream flows remain testable without live credentials.

Phase 1 now prefers real Google Geocoding, Street View, Places photo, Cloudflare R2 asset storage, and World Labs world generation when credentials are present.

Synthetic behavior remains available behind `MEDSENTINEL_USE_SYNTHETIC_FALLBACKS=true` for local or test workflows that should avoid external services.
