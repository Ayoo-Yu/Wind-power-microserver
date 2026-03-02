# API v1 Compatibility Mapping

This document defines the M1 compatibility mapping from legacy endpoints to `/api/v1/*`.

## Main Backend (Port 5000 / local 18080)

| Capability | Legacy Path | v1 Path | M1 Status | Notes |
|---|---|---|---|---|
| Health | `/health` | `/api/v1/health` | Implemented | v1 returns unified envelope; legacy remains available. |
| Farms (list) | `/api/farms` | `/api/v1/farms` | Implemented | v1 currently bridges to existing farms handler. |
| Auth | `/auth/*` | `/api/v1/auth/*` | Implemented | v1 and legacy share the same auth handlers via blueprint alias. |
| Fleet compare metrics | `/power-compare/fleet_metrics` | `/api/v1/power-compare/fleet_metrics` | Implemented | Multi-station MAE/RMSE/MSE aggregation by prediction type. |
| Fleet compare series | `/power-compare/fleet_series` | `/api/v1/power-compare/fleet_series` | Implemented | Multi-station overlay series for predicted/actual curves by prediction type. |

## AutoPredict Backend (Port 5001 / local 18081)

| Capability | Legacy Path | v1 Path | M1 Status | Notes |
|---|---|---|---|---|
| Health | `/health` | `/api/v1/health` | Implemented | v1 returns unified envelope format. |
| Auth | `/api/auth/*` | `/api/v1/auth/*` | Implemented | v1 and legacy share the same auth handlers via blueprint alias. |
| Farms | `/api/farms` | `/api/v1/autopredict/farms` | Implemented | Returns active farms from `wind_farms`, aligned with farm-code validation. |
| Runtime status | `/api/status` | `/api/v1/autopredict/status` | Implemented | v1 and legacy share same handler logic. |
| Fleet status | `/api/status_all` | `/api/v1/autopredict/status_all` | Implemented | Returns status snapshot for all active farms. |
| Fleet overview | `/api/overview` | `/api/v1/autopredict/overview` | Implemented | Returns fleet status with per-farm running task count. |
| Fleet control | `/api/control_all` | `/api/v1/autopredict/control_all` | Implemented | Batch `start/stop/delete` for same prediction type across selected farms. |
| Fleet matrix control | `/api/control_matrix` | `/api/v1/autopredict/control_matrix` | Implemented | Batch `start/stop/delete` across selected farms and selected prediction types. |
| Start task | `/api/start` | `/api/v1/autopredict/start` | Implemented | v1 and legacy share same handler logic. |
| Stop task | `/api/stop` | `/api/v1/autopredict/stop` | Implemented | v1 and legacy share same handler logic. |
| Schedule restart | `/api/schedule` | `/api/v1/autopredict/schedule` | Implemented | v1 and legacy share same handler logic. |
| Delete task | `/api/delete` | `/api/v1/autopredict/delete` | Implemented | v1 and legacy share same handler logic. |
| Logs | `/api/logs` | `/api/v1/autopredict/logs` | Implemented | v1 and legacy share same handler logic. |
| Resurrect PM2 | `/api/resurrect` | `/api/v1/autopredict/resurrect` | Implemented | v1 and legacy share same handler logic. |
| Save PM2 dump | `/api/save` | `/api/v1/autopredict/save` | Implemented | v1 and legacy share same handler logic. |
| Clear PM2 dump | `/api/clearsave` | `/api/v1/autopredict/clearsave` | Implemented | v1 and legacy share same handler logic. |
| Script info | `/api/script_info` | `/api/v1/autopredict/script_info` | Implemented | v1 and legacy share same handler logic. |
| Task history | `/api/history` | `/api/v1/autopredict/history` | Implemented | v1 and legacy share same handler logic. |
| Task status | `/api/task_status` | `/api/v1/autopredict/task_status` | Implemented | Handles missing `param` dir for short/medium safely. |

## Contract Notes

- Legacy endpoints remain valid during compatibility window (2 release cycles).
- `/api/v1/*` is the target namespace for incremental migration.
- Any added mapping must update this table in the same change set.
- Manual training/predict UI chain has been decommissioned in frontend and is intentionally not mapped into `/api/v1`.
- Duplicate concurrent control requests on same farm/task/action may return `409` (conflict guard).
- AutoPredict multi-station request and response contract is documented in:
  `docs/api/AUTOPREDICT_MULTI_STATION_CONTRACT.md`.
- Power compare multi-station contract is documented in:
  `docs/api/POWER_COMPARE_MULTI_STATION_CONTRACT.md`.
