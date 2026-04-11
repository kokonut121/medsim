# Security

## Required Posture

- IRIS should remain on an internal-only network in production.
- Findings and facility metadata should be encrypted at rest via IRIS Secure Wallet.
- Access should be role-scoped for SafetyOfficer, UnitManager, and Auditor.
- Audit logs must exist for read, write, and export actions.

## Development Scaffold Notes

- This repository uses a dev-safe in-memory persistence layer to mimic IRIS interfaces.
- `MEDSENTINEL_IRIS_MODE=memory` keeps all MedSentinel data in the local dev store.
- `MEDSENTINEL_IRIS_MODE=fhir` uses the live IRIS FHIR repository for interoperability while keeping MedSentinel domain storage in the local dev store, which is useful when native IRIS global access is not provisioned yet.
- `MEDSENTINEL_IRIS_MODE=native` uses direct IRIS globals plus the FHIR repository and requires the service account to have `%Native_GlobalAccess`.
- `iris/init.sh` and `iris/MedSentinelInstaller.cls` bootstrap a `MEDSENT` foundation namespace, FHIR endpoint, wallet collection, baseline roles, and the `medsent_app` service account when invoked through `./scripts/bootstrap-iris.sh` for local and shared-dev environments. The bootstrap-managed backend service role grants `%Native_GlobalAccess` so MedSentinel world models, scans, and findings persist in IRIS across backend restarts.
- Local Docker development intentionally avoids a durable IRIS data mount by default because InterSystems containers run as nonroot `irisowner` and require any mounted durable directory to be writable by UID `51773`.
- The wallet bootstrap currently creates a secure wallet collection and its access resources; full database-at-rest encryption and enterprise key management still need production-specific rollout work.
- Production rollouts must replace placeholders with real credential, role, TLS, and audit configurations.
