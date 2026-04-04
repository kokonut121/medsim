# Security

## Required Posture

- IRIS should remain on an internal-only network in production.
- Findings and facility metadata should be encrypted at rest via IRIS Secure Wallet.
- Access should be role-scoped for SafetyOfficer, UnitManager, and Auditor.
- Audit logs must exist for read, write, and export actions.

## Development Scaffold Notes

- This repository uses a dev-safe in-memory persistence layer to mimic IRIS interfaces.
- `iris/` contains placeholders for locked-down deployment, first-run setup, and FHIR server configuration.
- Production rollouts must replace placeholders with real credential, role, TLS, and audit configurations.

