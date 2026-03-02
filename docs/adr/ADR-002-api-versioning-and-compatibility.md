# ADR-002: API Versioning and Compatibility

## Status
Accepted

## Context
M1 introduces `/api/v1` compatibility skeleton while existing clients still rely on legacy endpoints.

## Decision
- Introduce versioned APIs under `/api/v1/*`.
- Keep existing legacy endpoints available during migration.
- Enforce strong backward compatibility for **2 release cycles** after v1 alternatives exist.

## Compatibility Rules
- Legacy endpoints remain callable and behavior-compatible during transition.
- New capabilities should be added on `/api/v1/*` first.
- Deprecation notices should be documented before removing any legacy endpoint.
- If behavior diverges, `/api/v1/*` is the canonical contract and mapping docs must be updated.

## Migration Guidance
- Migrate endpoints by capability group (health, farms, auth, etc.).
- Keep legacy auth paths temporarily to reduce risk.
- Publish mapping table in `docs/api/API_V1_COMPAT_MAPPING.md`.

