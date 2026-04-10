# Security

## Required Posture

- IRIS should remain on an internal-only network in production.
- Findings and facility metadata should be encrypted at rest via IRIS Secure Wallet.
- Access should be role-scoped for SafetyOfficer, UnitManager, and Auditor.
- Audit logs must exist for read, write, and export actions.

## Development Scaffold Notes

- This repository uses a dev-safe in-memory persistence layer to mimic IRIS interfaces.
- Native InterSystems wiring is available behind `MEDSENTINEL_IRIS_MODE=native`; production rollouts should still use locked-down networking, managed credentials, and audited roles.
- `iris/init.sh` and `iris/MedSentinelInstaller.cls` bootstrap a `MEDSENT` foundation namespace, FHIR endpoint, wallet collection, baseline roles, and the `medsent_app` service account when invoked through `./scripts/bootstrap-iris.sh` for local and shared-dev environments.
- Local Docker development intentionally avoids a durable IRIS data mount by default because InterSystems containers run as nonroot `irisowner` and require any mounted durable directory to be writable by UID `51773`.
- The wallet bootstrap currently creates a secure wallet collection and its access resources; full database-at-rest encryption and enterprise key management still need production-specific rollout work.
- Production rollouts must replace placeholders with real credential, role, TLS, and audit configurations.
