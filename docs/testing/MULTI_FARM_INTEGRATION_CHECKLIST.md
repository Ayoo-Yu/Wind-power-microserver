# Multi-Farm Integration Checklist

## Scope
This checklist validates multi-farm behavior across:
- Farm selector
- AutoPredict (single + batch + matrix)
- Power compare (main + fleet metrics + fleet series)
- API v1 compatibility fallback

## Preconditions
1. `kingbase` and required backend containers are running.
2. Main backend (5000 path via Nginx 8080) is reachable.
3. AutoPredict backend (5001 path via Nginx 8080) is reachable.
4. `wind_farms` table contains at least 2 active farms.
5. Login with a user that has access to `自动预测` and `功率对比`.

## Quick Start
1. Run local stack with your standard script: `wind-power-forecast/start-local.bat`.
2. Open frontend URL.
3. Login and confirm right-top farm selector is visible.

## A. Farm Selector
1. Open farm dropdown, verify farm list loads.
2. Switch farm A -> farm B.
3. Confirm no toast like `无效的场站代码`.
4. Refresh page and verify selected farm persists.

Expected:
- Selected farm updates immediately.
- No 400 error due to trailing spaces or case mismatch.

## B. AutoPredict - Single Farm
1. In `自动预测`, keep selected farm as farm A.
2. Run `status` query and one control action (`start`/`stop`) for a type.
3. Switch to farm B and repeat.

Expected:
- Status/control response includes requested `farm_code`.
- No false `无效的场站代码` for existing farms.

## C. AutoPredict - Multi-Farm Batch
1. Select at least 2 farms in batch controls.
2. Execute `control_all` for a prediction type.
3. Execute `control_matrix` for multiple types.
4. Export failed items CSV if any.

Expected:
- Summary counts match selected farm/type combinations.
- Per-item result includes `farm_code`, `status_code`, `message`.

## D. Power Compare - Main
1. In `功率对比`, select time range and load main chart for farm A.
2. Switch to farm B and load again.
3. Compare chart curves / metrics output.

Expected:
- Main endpoint uses `farm_code` filter.
- Different farms can produce different results under same time range.

## E. Power Compare - Fleet
1. Choose 2+ farms in fleet section.
2. Run fleet metrics compare.
3. Run fleet series compare with `include_actual` on/off.
4. Export fleet CSV.

Expected:
- Fleet metrics rows are per farm.
- Fleet series contains per-farm predicted/actual arrays.

## F. v1 Compatibility
Use browser devtools Network and verify requests can succeed with:
1. `/api/v1/power-compare/data`
2. `/api/v1/power-compare/fleet_metrics`
3. `/api/v1/power-compare/fleet_series`
4. `/api/v1/farms`
5. `/api/v1/farms/{farm_code}`
6. `/api/v1/farms/{farm_code}/stats`
7. `/api/v1/autopredict/*`

Expected:
- v1 path works.
- If v1 endpoint unavailable, frontend fallback path still works.

## G. Regression Checks
1. Login/logout flow still works.
2. User management page still loads users and roles.
3. Existing report/weather/system pages still open without JS runtime errors.

## Pass Criteria
- All sections A~G complete without blocking error.
- No critical 4xx/5xx on normal user flow.
- Farm switching is stable and deterministic.
