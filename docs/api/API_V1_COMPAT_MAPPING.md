# API v1 Compatibility Mapping

This document defines the M1 compatibility mapping from legacy endpoints to `/api/v1/*`.

## Main Backend (Port 5000 / local 18080)

| Capability | Legacy Path | v1 Path | M1 Status | Notes |
|---|---|---|---|---|
| Health | `/health` | `/api/v1/health` | Implemented | v1 returns unified envelope; legacy remains available. |
| Farms (list) | `/api/farms` | `/api/v1/farms` | Implemented | v1 currently bridges to existing farms handler. |
| Auth | `/auth/*` | `/api/v1/auth/*` | Pending | Legacy auth path retained in M1. |

## AutoPredict Backend (Port 5001 / local 18081)

| Capability | Legacy Path | v1 Path | M1 Status | Notes |
|---|---|---|---|---|
| Health | `/health` | `/api/v1/health` | Pending | Legacy health remains; v1 endpoint not added in M1. |
| Auth | `/api/auth/*` | `/api/v1/auth/*` | Pending | Keep legacy path; migrate in later milestone. |
| Task status | `/api/task_status` | `/api/v1/autopredict/task_status` | Pending | M1 focuses on response envelope compatibility first. |
| Runtime status | `/api/status` | `/api/v1/autopredict/status` | Pending | Keep legacy contract stable during migration window. |

## Contract Notes

- Legacy endpoints remain valid during compatibility window (2 release cycles).
- `/api/v1/*` is the target namespace for incremental migration.
- Any added mapping must update this table in the same change set.
- AutoPredict multi-station request and response contract is documented in:
  `docs/api/AUTOPREDICT_MULTI_STATION_CONTRACT.md`.
