# Power Compare Multi-Station Contract

## Scope
This contract defines multi-station comparison behavior for data visualization.

## Endpoint
- Legacy: `POST /power-compare/data`
- v1 bridge: `POST /api/v1/power-compare/data`
- Legacy: `POST /power-compare/fleet_metrics`
- v1 bridge: `POST /api/v1/power-compare/fleet_metrics`
- Legacy: `POST /power-compare/fleet_series`
- v1 bridge: `POST /api/v1/power-compare/fleet_series`

## Request
```json
{
  "start": "2026-03-01 00:00:00",
  "end": "2026-03-01 23:59:59",
  "farm_codes": ["farm_a", "farm_b"],
  "prediction_type": "short"
}
```

Rules:
- `start` and `end` are required.
- `farm_codes` is optional.
- If `farm_codes` is omitted or empty, backend uses all active farms.
- `prediction_type` supports `short`, `mid`, `supershort`.

## Main Compare Data Request (single farm scoped)
```json
{
  "start": "2026-03-01 00:00:00",
  "end": "2026-03-01 23:59:59",
  "types": ["实测值", "短期预测", "中期预测"],
  "farm_code": "farm_a",
  "supershort_horizon": "average"
}
```

Rules:
- `farm_code` is optional.
- If `farm_code` is provided, backend filters all selected series by that farm.
- If omitted, backend behavior remains compatible with existing legacy flow.

## Response
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "farm_code": "farm_a",
        "farm_name": "Farm A",
        "actual_points": 96,
        "predicted_points": 96,
        "points": 96,
        "mae": 12.3,
        "rmse": 15.8,
        "mse": 249.6
      }
    ],
    "count": 1,
    "prediction_type": "short"
  }
}
```

Notes:
- `items` are sorted by ascending `rmse` (best first).
- `points` is aligned timestamp count between actual and prediction series.

## Fleet Series Request
```json
{
  "start": "2026-03-01 00:00:00",
  "end": "2026-03-01 23:59:59",
  "farm_codes": ["farm_a", "farm_b"],
  "prediction_type": "short",
  "include_actual": true
}
```

## Fleet Series Response
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "farm_code": "farm_a",
        "farm_name": "Farm A",
        "predicted": [{"timestamp": "2026-03-01T00:00:00", "power": 120.5}],
        "actual": [{"timestamp": "2026-03-01T00:00:00", "power": 118.2}]
      }
    ],
    "count": 1,
    "prediction_type": "short",
    "include_actual": true
  }
}
```
