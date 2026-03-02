# Autopredict Multi-Station Contract

## Scope
This contract defines the current autopredict API behavior for multi-station usage.
It applies to the autopredict backend endpoints proxied from frontend `/api/*` routes.

## Farm Context Rule
- All task and status operations are farm-scoped.
- Request field `farm_code` is recommended on every request.
- If `farm_code` is omitted, backend resolves it with fallback:
1. Prefer `DEFAULT_FARM` if active.
2. Otherwise use the first active farm from `wind_farms`.

## Endpoint Contract

| Endpoint | Method | Farm Scope | Notes |
|---|---|---|---|
| `/api/farms` | `GET` | N/A | Returns active farms from `wind_farms` as selector source-of-truth. |
| `/api/status` | `GET` | Query by `farm_code` | Returns current task statuses and `farm_code`. |
| `/api/status_all` | `GET` | N/A | Returns all active farms with per-farm task status snapshot. |
| `/api/start` | `POST` | Body `farm_code` | Starts task process as `<farm_code>_<script_name>`. |
| `/api/stop` | `POST` | Body `farm_code` | Stops only the scoped process. |
| `/api/delete` | `POST` | Body `farm_code` | Deletes only the scoped process in PM2. |
| `/api/schedule` | `POST` | Body `farm_code` | Schedules scoped process restart. |
| `/api/script_info` | `GET` | Query `farm_code` | Reads info from scoped process name. |
| `/api/logs` | `GET` | Query `farm_code` | Filters logs by farm context where supported. |

## Response Envelope
- Current standard envelope:
`{ "code": <int>, "message": <string>, "data": <object|null> }`
- During compatibility window, several endpoints still expose legacy top-level fields
  (for example `farm_code`, `short`, `logs`).
- New clients should read `data` first, then fallback to legacy fields only if needed.

## Validation Rule
- Backend validates `farm_code` against active farm list from database (`wind_farms`).
- Invalid `farm_code` must return `400`.
- Concurrent duplicate operation on same `farm_code + prediction_type + action` returns `409` with conflict code.

## Process Naming Rule
- PM2 process names use pattern:
`<farm_code>_<script_name>`
- This prevents cross-farm task collisions and allows independent control.
- Same prediction type can run concurrently for different farms, because process scope is farm-specific.

## Frontend Requirement
- Frontend should always include `farm_code` from selected farm state.
- Shared wrapper `frontend/src/api/autopredictApi.js` is the single entry for autopredict API calls.
