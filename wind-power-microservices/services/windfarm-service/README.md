# Wind Farm Management Service

A microservice for managing wind farms and turbines in a distributed wind power forecasting system.

## Features

- **Wind Farm Management**: CRUD operations for wind farms with comprehensive validation
- **Turbine Management**: Individual turbine management within wind farms
- **User Management**: Authentication, authorization, and role-based access control
- **Multi-Windfarm Support**: Support for managing multiple wind farms with access control
- **Real-time Data**: Integration points for SCADA data and real-time monitoring
- **Audit Logging**: Comprehensive audit trail for all operations
- **Health Monitoring**: Built-in health checks and metrics
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation

## Architecture

This service follows Domain-Driven Design (DDD) principles and implements:

- **Clean Architecture**: Separation of concerns with distinct layers
- **Repository Pattern**: Database abstraction with CRUD operations
- **Service Layer**: Business logic separated from API endpoints
- **Event-Driven**: Integration points for event publishing
- **Microservice Patterns**: Circuit breaker, rate limiting, health checks

## Technology Stack

- **Framework**: FastAPI (async Python web framework)
- **Database**: PostgreSQL with SQLAlchemy ORM (async)
- **Cache**: Redis for session management and caching
- **Authentication**: JWT tokens with role-based access control
- **Validation**: Pydantic models with comprehensive validation
- **Documentation**: Auto-generated OpenAPI/Swagger UI
- **Containerization**: Docker and Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL 15+ (if running locally)
- Redis 7+ (if running locally)

### Using Docker Compose (Recommended)

1. Clone the repository and navigate to the service directory:
```bash
cd wind-power-microservices/services/windfarm-service
```

2. Copy the environment file:
```bash
cp .env.example .env
```

3. Start the services:
```bash
docker-compose up -d
```

4. Access the service:
- API: http://localhost:8001
- API Documentation: http://localhost:8001/docs
- Health Check: http://localhost:8001/health

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up PostgreSQL and Redis

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run database migrations:
```bash
alembic upgrade head
```

5. Start the service:
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8001
```

## API Endpoints

### Wind Farms

- `GET /api/v1/wind-farms` - List wind farms with filtering and pagination
- `POST /api/v1/wind-farms` - Create new wind farm
- `GET /api/v1/wind-farms/{id}` - Get wind farm by ID
- `PUT /api/v1/wind-farms/{id}` - Update wind farm
- `DELETE /api/v1/wind-farms/{id}` - Delete wind farm
- `GET /api/v1/wind-farms/{id}/statistics` - Get wind farm statistics
- `GET /api/v1/wind-farms/search/{query}` - Search wind farms
- `GET /api/v1/wind-farms/by-status/{status}` - Get wind farms by status

### Turbines

- `GET /api/v1/turbines` - List turbines with filtering and pagination
- `POST /api/v1/turbines` - Create new turbine
- `GET /api/v1/turbines/{id}` - Get turbine by ID
- `PUT /api/v1/turbines/{id}` - Update turbine
- `DELETE /api/v1/turbines/{id}` - Delete turbine
- `GET /api/v1/turbines/by-wind-farm/{wind_farm_id}` - Get turbines by wind farm
- `GET /api/v1/turbines/{id}/statistics` - Get turbine statistics
- `POST /api/v1/turbines/{id}/control/{action}` - Control turbine (start/stop/reset)

### Users & Authentication

- `POST /api/v1/users/register` - Register new user
- `POST /api/v1/users/login` - User login
- `POST /api/v1/users/refresh` - Refresh access token
- `GET /api/v1/users/me` - Get current user info
- `GET /api/v1/users` - List users (admin only)
- `GET /api/v1/users/{id}` - Get user by ID
- `PUT /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Delete user (admin only)

### Health & Monitoring

- `GET /health` - Overall health check
- `GET /health/ready` - Readiness check
- `GET /health/live` - Liveness check
- `GET /health/dependencies` - Dependency health check
- `GET /health/metrics` - Service metrics

## Data Models

### Wind Farm
```json
{
  "id": "string",
  "code": "string",
  "name": "string",
  "description": "string",
  "location": "string",
  "latitude": "number",
  "longitude": "number",
  "total_capacity": "number",
  "turbine_count": "integer",
  "commissioning_date": "string",
  "contact_email": "string",
  "contact_phone": "string",
  "address": "string",
  "status": "active|inactive|maintenance|...",
  "current_power": "number",
  "running_turbines": "integer",
  "created_at": "string",
  "updated_at": "string"
}
```

### Wind Turbine
```json
{
  "id": "string",
  "turbine_id": "string",
  "wind_farm_id": "string",
  "manufacturer": "string",
  "model": "string",
  "rated_power": "number",
  "rotor_diameter": "number",
  "hub_height": "number",
  "latitude": "number",
  "longitude": "number",
  "commissioning_date": "string",
  "status": "running|stopped|maintenance|...",
  "current_power": "number",
  "wind_speed": "number",
  "rotor_speed": "number",
  "availability": "number",
  "created_at": "string",
  "updated_at": "string"
}
```

## Authentication & Authorization

The service implements JWT-based authentication with role-based access control:

### User Roles
- **Viewer**: Read-only access to assigned wind farms
- **Analyst**: View and analyze data for assigned wind farms
- **Operator**: Full access to turbines (control operations) in assigned wind farms
- **Admin**: Full access to wind farms and user management

### Access Control
- Users can only access wind farms they have been granted access to
- Role-based permissions determine what operations users can perform
- Superusers have access to all wind farms and full administrative privileges

## Configuration

The service can be configured through environment variables (see `.env.example`):

### Key Configuration Options
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `SECRET_KEY`: JWT secret key
- `JWT_EXPIRATION_MINUTES`: JWT token expiration time
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `CORS_ORIGINS`: Allowed CORS origins
- `RATE_LIMIT_PER_MINUTE`: API rate limiting

## Development

### Project Structure
```
src/
├── __init__.py
├── main.py              # FastAPI application entry point
├── config.py            # Configuration management
├── database.py          # Database models and connection
├── models.py            # Pydantic data models
├── auth.py              # Authentication and authorization
├── utils.py             # Utility functions
├── exceptions.py        # Custom exceptions
├── routers/             # API endpoint definitions
│   ├── __init__.py
│   ├── wind_farms.py   # Wind farm endpoints
│   ├── turbines.py     # Turbine endpoints
│   ├── users.py        # User management endpoints
│   └── health.py       # Health check endpoints
└── services/            # Business logic
    ├── __init__.py
    ├── wind_farm_service.py
    ├── turbine_service.py
    ├── user_service.py
    └── access_service.py
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_wind_farm_service.py
```

### Code Quality
```bash
# Format code
black src/

# Sort imports
isort src/

# Lint code
flake8 src/

# Type checking
mypy src/
```

## Deployment

### Kubernetes
See `k8s/` directory for Kubernetes deployment manifests:
- Deployment configuration
- Service configuration
- ConfigMap and Secrets
- Horizontal Pod Autoscaler

### Docker
```bash
# Build image
docker build -t windfarm-service:latest .

# Run container
docker run -p 8001:8001 --env-file .env windfarm-service:latest
```

## Monitoring

### Health Checks
The service provides comprehensive health checks:
- `/health` - Overall service health
- `/health/ready` - Readiness probe for Kubernetes
- `/health/live` - Liveness probe for Kubernetes
- `/health/dependencies` - Dependency health (database, Redis)

### Metrics
When enabled, the service exposes Prometheus metrics at `/metrics` endpoint.

### Logging
Structured logging with configurable levels and formats for easy integration with log aggregation systems.

## Integration

### SCADA Data Service Integration
The service provides integration points for real-time SCADA data:
- Real-time turbine status and power output
- Wind speed and environmental data
- Operational metrics and alarms

### Event Publishing
The service can publish events to message queues for:
- Wind farm creation/updates
- Turbine status changes
- User access changes
- System alerts and notifications

## Troubleshooting

### Common Issues

1. **Database Connection Issues**
   - Check DATABASE_URL configuration
   - Verify PostgreSQL is running and accessible
   - Check database credentials

2. **Redis Connection Issues**
   - Check REDIS_URL configuration
   - Verify Redis is running and accessible

3. **Authentication Issues**
   - Verify SECRET_KEY is properly configured
   - Check JWT token expiration settings
   - Ensure user accounts are active

### Debug Mode
Enable debug mode by setting `DEBUG=true` in the environment for detailed logging and error messages.

## Contributing

See the main repository's CONTRIBUTING.md for guidelines on contributing to this microservice.

## License

This service is part of the Wind Power Forecasting System and follows the same licensing terms. See the main repository's LICENSE file for details.