# API v1 Compatibility Mapping

This document defines the M1 compatibility mapping from legacy endpoints to `/api/v1/*`.

## Main Backend (Port 5000 / local 18080)

| Capability | Legacy Path | v1 Path | M1 Status | Notes |
|---|---|---|---|---|
| Health | `/health` | `/api/v1/health` | Implemented | v1 returns unified envelope; legacy remains available. |
| Farms (list) | `/api/farms` | `/api/v1/farms` | Implemented | v1 currently bridges to existing farms handler. |
| Farm detail | `/api/farms/{farm_code}` | `/api/v1/farms/{farm_code}` | Implemented | Returns single farm metadata by farm code. |
| Farm stats | `/api/farms/{farm_code}/stats` | `/api/v1/farms/{farm_code}/stats` | Implemented | `/statistics` alias remains supported for compatibility. |
| Auth | `/auth/*` | `/api/v1/auth/*` | Implemented | v1 and legacy share the same auth handlers via blueprint alias. |
| Fleet compare metrics | `/power-compare/fleet_metrics` | `/api/v1/power-compare/fleet_metrics` | Implemented | Multi-station MAE/RMSE/MSE aggregation by prediction type. |
| Fleet compare series | `/power-compare/fleet_series` | `/api/v1/power-compare/fleet_series` | Implemented | Multi-station overlay series for predicted/actual curves by prediction type. |
| Power compare main data | `/power-compare/data` | `/api/v1/power-compare/data` | Implemented | Main comparison timeseries endpoint now available in v1 compat bridge. |
| Report farms (list/create/update) | `/api/report/farms*` | `/api/v1/report/farms*` | Implemented | Includes list, create, and update by farm id. |
| Report configs (CRUD) | `/api/report/configs*` | `/api/v1/report/configs*` | Implemented | Includes list/create/update/delete by config id. |
| Report logs | `/api/report/logs` | `/api/v1/report/logs` | Implemented | Supports same query filters and paging. |
| Report preview/manual | `/api/report/preview-report` `/api/report/manual-report` | `/api/v1/report/preview-report` `/api/v1/report/manual-report` | Implemented | Same payload contracts via compat bridge. |
| Report scheduler | `/api/report/scheduler/*` | `/api/v1/report/scheduler/*` | Implemented | Supports `start`, `stop`, `status`. |
| Report statistics | `/api/report/statistics` | `/api/v1/report/statistics` | Implemented | Daily and monthly quality metrics. |
| Physical simulation query | `/physical_simulation/{conditions|turbines|readings}` | `/api/v1/physical-simulation/{conditions|turbines|readings}` | Implemented | Supports `farm_name`, `condition_id`, `turbine_id` query parameters. |
| Physical simulation batch import | `/physical_simulation/{turbines|conditions|readings}/batch` | `/api/v1/physical-simulation/{turbines|conditions|readings}/batch` | Implemented | CSV batch import endpoints are available in v1 compat namespace. |
| System maintenance info | `/api/system/{hardware|software|runtime|logs}` | `/api/v1/system/{hardware|software|runtime|logs}` | Implemented | Reuses existing system info handlers via v1 compat bridge. |
| Weather fetch connections | `/api/weather-fetch/connections*` | `/api/v1/weather-fetch/connections*` | Implemented | Includes list/create/update/delete/test connection endpoints. |
| Weather fetch tasks | `/api/weather-fetch/tasks*` | `/api/v1/weather-fetch/tasks*` | Implemented | Includes list/create/update/delete/toggle/run and task logs endpoints. |
| Weather fetch scheduler | `/api/weather-fetch/scheduler/*` | `/api/v1/weather-fetch/scheduler/*` | Implemented | Supports `status` and `restart`. |
| Weather fetch utility | `/api/weather-fetch/check-directories` `/api/weather-fetch/stats` | `/api/v1/weather-fetch/check-directories` `/api/v1/weather-fetch/stats` | Implemented | Directory probe and task statistics endpoints. |

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
