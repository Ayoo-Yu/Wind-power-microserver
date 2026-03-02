# API v1 Compatibility Mapping

This document defines the first-round mapping from legacy endpoints to `/api/v1/*`.

## Mapping Table (M1)

| Capability | Legacy Path | v1 Path | M1 Status | Notes |
|---|---|---|---|---|
| Health | `/health` | `/api/v1/health` | Implemented | Legacy stays available. |
| Farms (list) | `/api/farms` | `/api/v1/farms` | Implemented | v1 currently proxies existing farms handler behavior. |
| Auth | `/auth/*` | `/api/v1/auth/*` | Pending | Legacy auth paths are kept unchanged in M1. |

## Contract Notes
- Legacy endpoints remain valid during compatibility window (2 release cycles).
- `/api/v1/*` is the target namespace for future evolution.
- Any added mapping must update this table in the same change set.
- Autopredict multi-station contract is documented in:
  `docs/api/AUTOPREDICT_MULTI_STATION_CONTRACT.md`
