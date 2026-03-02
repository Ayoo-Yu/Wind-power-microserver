# Power Compare Multi-Station Contract

## Scope
This contract defines multi-station comparison behavior for data visualization.

## Endpoint
- Legacy: `POST /power-compare/fleet_metrics`
- v1 bridge: `POST /api/v1/power-compare/fleet_metrics`

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
