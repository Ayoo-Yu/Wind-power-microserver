# Wind Power Microservices API Documentation

## Overview
This document describes the API endpoints for the wind power forecasting system, all accessible through the Kong API Gateway at `http://localhost:8000`.

## Authentication
All API endpoints require JWT authentication unless otherwise specified.

### Getting JWT Token
```bash
# Login to get JWT token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "password": "your_password"
  }'
```

### Using JWT Token
Include the JWT token in the Authorization header:
```bash
curl -X GET http://localhost:8000/api/v1/weather-stations \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## API Endpoints

### 1. Meteorological Service
Base path: `/api/v1/weather-*`

#### Weather Stations
- **GET** `/api/v1/weather-stations`
  - Get all weather stations
  - Response: Array of weather station objects

- **POST** `/api/v1/weather-stations`
  - Create new weather station
  - Body: Weather station object

- **PUT** `/api/v1/weather-stations/{id}`
  - Update weather station
  - Body: Updated weather station object

- **DELETE** `/api/v1/weather-stations/{id}`
  - Delete weather station

#### Weather Data
- **GET** `/api/v1/weather-data`
  - Get weather data with filtering
  - Query params: `station_id`, `start_date`, `end_date`, `limit`

- **POST** `/api/v1/weather-data`
  - Submit new weather data
  - Body: Weather data object

#### Forecasts
- **GET** `/api/v1/forecasts`
  - Get weather forecasts
  - Query params: `station_id`, `forecast_date`, `days_ahead`

- **POST** `/api/v1/forecasts`
  - Create weather forecast
  - Body: Forecast object

### 2. SCADA Service
Base path: `/api/v1/scada-*`

#### SCADA Data
- **GET** `/api/v1/scada-data`
  - Get SCADA sensor data
  - Query params: `turbine_id`, `sensor_type`, `start_time`, `end_time`

- **POST** `/api/v1/scada-data`
  - Submit SCADA data
  - Body: SCADA data object

#### SCADA Alerts
- **GET** `/api/v1/scada-alerts`
  - Get SCADA alerts
  - Query params: `turbine_id`, `severity`, `status`

- **POST** `/api/v1/scada-alerts`
  - Create SCADA alert
  - Body: Alert object

- **PUT** `/api/v1/scada-alerts/{id}`
  - Update alert status
  - Body: Updated alert object

- **DELETE** `/api/v1/scada-alerts/{id}`
  - Delete SCADA alert

### 3. Power Prediction Service
Base path: `/api/v1/predictions` and `/api/v1/ml-models`

#### Predictions
- **GET** `/api/v1/predictions`
  - Get power predictions
  - Query params: `wind_farm_id`, `turbine_id`, `prediction_date`, `horizon_hours`

- **POST** `/api/v1/predictions`
  - Generate power prediction
  - Body: Prediction request object

#### ML Models
- **GET** `/api/v1/ml-models`
  - Get available ML models
  - Query params: `model_type`, `status`

- **POST** `/api/v1/ml-models`
  - Create new ML model
  - Body: Model configuration object

- **PUT** `/api/v1/ml-models/{id}`
  - Update ML model
  - Body: Updated model object

- **DELETE** `/api/v1/ml-models/{id}`
  - Delete ML model

### 4. Report Service
Base path: `/api/v1/reports`, `/api/v1/charts`, `/api/v1/templates`

#### Reports
- **GET** `/api/v1/reports`
  - Get reports list
  - Query params: `report_type`, `date_range`, `status`

- **POST** `/api/v1/reports`
  - Generate new report
  - Body: Report generation request

- **PUT** `/api/v1/reports/{id}`
  - Update report
  - Body: Updated report object

- **DELETE** `/api/v1/reports/{id}`
  - Delete report

#### Charts
- **GET** `/api/v1/charts`
  - Get available charts
  - Query params: `chart_type`, `data_source`

- **POST** `/api/v1/charts`
  - Create new chart
  - Body: Chart configuration object

- **DELETE** `/api/v1/charts/{id}`
  - Delete chart

#### Templates
- **GET** `/api/v1/templates`
  - Get report templates
  - Query params: `template_type`, `category`

- **POST** `/api/v1/templates`
  - Create new template
  - Body: Template object

- **PUT** `/api/v1/templates/{id}`
  - Update template
  - Body: Updated template object

- **DELETE** `/api/v1/templates/{id}`
  - Delete template

### 5. Tenant Service
Base path: `/api/v1/auth` and `/api/v1/users`

#### Authentication
- **POST** `/api/v1/auth/login`
  - User login (no JWT required)
  - Body: `{ "username": "string", "password": "string" }`
  - Response: JWT token and user info

- **POST** `/api/v1/auth/logout`
  - User logout
  - Headers: Authorization: Bearer {token}

- **POST** `/api/v1/auth/refresh`
  - Refresh JWT token
  - Headers: Authorization: Bearer {token}

#### Users
- **GET** `/api/v1/users`
  - Get users list
  - Query params: `role`, `status`, `tenant_id`

- **POST** `/api/v1/users`
  - Create new user
  - Body: User object

- **PUT** `/api/v1/users/{id}`
  - Update user
  - Body: Updated user object

- **DELETE** `/api/v1/users/{id}`
  - Delete user

#### Tenants
- **GET** `/api/v1/tenants`
  - Get tenants list
  - Query params: `status`, `plan_type`

- **POST** `/api/v1/tenants`
  - Create new tenant
  - Body: Tenant object

- **PUT** `/api/v1/tenants/{id}`
  - Update tenant
  - Body: Updated tenant object

- **DELETE** `/api/v1/tenants/{id}`
  - Delete tenant

### 6. Wind Farm Service
Base path: `/api/v1/wind-farms` and `/api/v1/turbines`

#### Wind Farms
- **GET** `/api/v1/wind-farms`
  - Get wind farms list
  - Query params: `status`, `location`, `capacity_min`, `capacity_max`

- **POST** `/api/v1/wind-farms`
  - Create new wind farm
  - Body: Wind farm object

- **PUT** `/api/v1/wind-farms/{id}`
  - Update wind farm
  - Body: Updated wind farm object

- **DELETE** `/api/v1/wind-farms/{id}`
  - Delete wind farm

#### Turbines
- **GET** `/api/v1/turbines`
  - Get turbines list
  - Query params: `wind_farm_id`, `status`, `model`

- **POST** `/api/v1/turbines`
  - Create new turbine
  - Body: Turbine object

- **PUT** `/api/v1/turbines/{id}`
  - Update turbine
  - Body: Updated turbine object

- **DELETE** `/api/v1/turbines/{id}`
  - Delete turbine

## Health Check Endpoints

All services provide health check endpoints:

- **GET** `/health` - Service health status
- **GET** `/health/ready` - Readiness probe
- **GET** `/health/live` - Liveness probe

## Rate Limiting

API endpoints are rate-limited:
- 1000 requests per minute per consumer
- 10000 requests per hour per consumer

## CORS Configuration

All endpoints support CORS with the following configuration:
- Allowed origins: `*`
- Allowed methods: `GET, POST, PUT, DELETE, OPTIONS`
- Allowed headers: `Content-Type, Authorization, X-Requested-With`

## Response Format

All API responses follow this format:
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation successful",
  "timestamp": "2024-01-01T00:00:00.000Z"
}
```

Error responses:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": { ... }
  },
  "timestamp": "2024-01-01T00:00:00.000Z"
}
```

## Error Codes

- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Validation Error
- `429` - Too Many Requests
- `500` - Internal Server Error

## Testing

Use the provided test script to validate API gateway functionality:
```bash
# Run comprehensive tests
./scripts/test-api-gateway.sh

# Test with custom URLs
./scripts/test-api-gateway.sh --kong-admin-url http://kong:8001 --kong-proxy-url http://kong:8000
```

## Monitoring

Kong provides metrics at:
- **GET** `http://localhost:8001/metrics` - Prometheus metrics
- **GET** `http://localhost:8001/status` - Kong status

Access Konga GUI for management:
- URL: `http://localhost:1337`
- Default credentials: admin/konga