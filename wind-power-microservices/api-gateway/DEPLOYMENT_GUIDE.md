# Kong API Gateway Deployment Guide

## Overview
This guide provides step-by-step instructions for deploying the Kong API Gateway for the wind power forecasting system.

## Prerequisites

### System Requirements
- Docker 20.10+
- Docker Compose 1.29+
- 4GB RAM minimum
- 2 CPU cores minimum
- 10GB disk space

### Network Requirements
- Ports 8000, 8001, 8002, 5432, 6379, 1337 available
- Internal network connectivity between services

## Quick Start

### 1. Clone and Navigate
```bash
cd wind-power-microservices/api-gateway
```

### 2. Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit environment variables
nano .env
```

### 3. Start Services
```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

### 4. Initialize Kong
```bash
# Wait for database to be ready (30-60 seconds)
sleep 30

# Run initialization script
./scripts/init-kong.sh

# Verify initialization
./scripts/health-check.sh
```

### 5. Test Configuration
```bash
# Run comprehensive tests
./scripts/test-api-gateway.sh

# Check Kong status
curl http://localhost:8001/status
```

## Detailed Deployment

### Step 1: Database Setup
```bash
# Start database first
docker-compose up -d kong-db

# Wait for database initialization
./scripts/wait-for-db.sh
```

### Step 2: Kong Migration
```bash
# Run database migrations
docker-compose run --rm kong-migration

# Verify migrations
docker-compose logs kong-migration
```

### Step 3: Kong Startup
```bash
# Start Kong
docker-compose up -d kong

# Check Kong logs
docker-compose logs -f kong
```

### Step 4: Service Configuration
```bash
# Configure all services
./scripts/init-kong.sh

# Verify service configuration
./scripts/kong-manager.py --command services
```

### Step 5: Supporting Services
```bash
# Start Redis
docker-compose up -d redis

# Start Konga GUI
docker-compose up -d konga
```

## Configuration

### Environment Variables
Create a `.env` file with the following variables:

```bash
# Kong Configuration
KONG_ADMIN_URL=http://localhost:8001
KONG_PROXY_URL=http://localhost:8000
KONG_DATABASE=postgres
KONG_PG_HOST=kong-db
KONG_PG_PORT=5432
KONG_PG_USER=kong
KONG_PG_PASSWORD=kong
KONG_PG_DATABASE=kong

# Database Configuration
POSTGRES_DB=kong
POSTGRES_USER=kong
POSTGRES_PASSWORD=kong

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379

# Konga Configuration
KONGA_DB_ADAPTER=postgres
KONGA_DB_HOST=kong-db
KONGA_DB_PORT=5432
KONGA_DB_USER=kong
KONGA_DB_PASSWORD=kong
KONGA_DB_DATABASE=konga
```

### Kong Configuration (kong.conf)
Key configuration options in `config/kong.conf`:

```conf
# Database
database = postgres
pg_host = kong-db
pg_port = 5432
pg_user = kong
pg_password = kong
pg_database = kong

# Security
admin_listen = 0.0.0.0:8001
proxy_listen = 0.0.0.0:8000, 0.0.0.0:8443 ssl
admin_gui_listen = 0.0.0.0:8002

# Plugins
plugins = bundled,jwt-custom,prometheus,rate-limiting,cors

# Rate Limiting
nginx_worker_processes = auto
```

## Service Configuration

### Declarative Configuration
The `declarative/kong.yml` file contains all service configurations:

- 6 microservices with routes
- JWT authentication
- Rate limiting (1000/min, 10000/hour)
- CORS configuration
- Prometheus metrics

### Services Overview
1. **Meteorological Service** - Weather data and forecasts
2. **SCADA Service** - Real-time sensor data
3. **Power Prediction Service** - ML-based power predictions
4. **Report Service** - Reports and analytics
5. **Tenant Service** - User management and authentication
6. **Wind Farm Service** - Wind farm and turbine management

## Security Configuration

### JWT Authentication
- Custom JWT plugin implementation
- Token validation with signature verification
- Claim validation and consumer headers
- Automatic key rotation support

### Rate Limiting
- Local policy with Redis fallback
- 1000 requests per minute per consumer
- 10000 requests per hour per consumer
- Per-service rate limiting available

### CORS Configuration
- Allowed origins: `*`
- Allowed methods: `GET, POST, PUT, DELETE, OPTIONS`
- Allowed headers: `Content-Type, Authorization, X-Requested-With`
- Preflight caching: 3600 seconds

## Monitoring and Management

### Health Checks
```bash
# Kong health check
curl http://localhost:8001/status

# Service health check
./scripts/health-check.sh

# API gateway tests
./scripts/test-api-gateway.sh
```

### Metrics Collection
- Prometheus metrics available at `http://localhost:8001/metrics`
- Service-level metrics for each microservice
- Rate limiting and authentication metrics
- Performance and latency metrics

### Konga GUI Management
- URL: `http://localhost:1337`
- Default credentials: `admin/konga`
- Service configuration management
- Plugin management
- Consumer and credential management
- Real-time monitoring

## Troubleshooting

### Common Issues

#### 1. Database Connection Issues
```bash
# Check database status
docker-compose logs kong-db

# Test database connectivity
docker exec -it api-gateway_kong-db_1 psql -U kong -d kong -c "SELECT version();"
```

#### 2. Kong Startup Issues
```bash
# Check Kong logs
docker-compose logs kong

# Verify configuration
docker exec -it api-gateway_kong_1 kong check
```

#### 3. Service Registration Issues
```bash
# Re-run initialization
./scripts/init-kong.sh

# Check service configuration
./scripts/kong-manager.py --command services
```

#### 4. JWT Authentication Issues
```bash
# Test JWT plugin
./scripts/test-api-gateway.sh --test jwt

# Check consumer credentials
./scripts/kong-manager.py --command consumers
```

### Log Analysis
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f kong
docker-compose logs -f kong-db

# View initialization logs
./scripts/init-kong.sh | tee init.log
```

## Scaling and Performance

### Horizontal Scaling
```bash
# Scale Kong instances
docker-compose up -d --scale kong=3

# Configure load balancer
# Update upstream configuration in kong.yml
```

### Performance Tuning
- Adjust `nginx_worker_processes` based on CPU cores
- Configure connection pooling
- Enable HTTP/2 support
- Optimize database connections

## Backup and Recovery

### Database Backup
```bash
# Backup PostgreSQL database
docker exec api-gateway_kong-db_1 pg_dump -U kong kong > kong_backup.sql

# Backup Konga database
docker exec api-gateway_kong-db_1 pg_dump -U kong konga > konga_backup.sql
```

### Configuration Backup
```bash
# Backup Kong configuration
cp -r config/ config_backup/
cp -r declarative/ declarative_backup/
```

### Recovery
```bash
# Restore database
docker exec -i api-gateway_kong-db_1 psql -U kong kong < kong_backup.sql

# Restore configuration
cp -r config_backup/* config/
```

## Production Deployment

### Security Hardening
1. Change default passwords
2. Enable SSL/TLS certificates
3. Configure firewall rules
4. Set up monitoring and alerting
5. Implement log aggregation

### High Availability
1. Deploy multiple Kong instances
2. Use external database cluster
3. Configure Redis cluster for rate limiting
4. Set up load balancer
5. Implement health checks

### Monitoring Setup
1. Configure Prometheus metrics
2. Set up Grafana dashboards
3. Configure alerting rules
4. Implement log shipping
5. Set up distributed tracing

## API Usage Examples

### Service Health Check
```bash
curl http://localhost:8000/health
```

### Authenticated Request
```bash
# Get JWT token first
token=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}' | jq -r '.token')

# Use token for API request
curl -X GET http://localhost:8000/api/v1/weather-stations \
  -H "Authorization: Bearer $token"
```

### Generate Report
```bash
curl -X POST http://localhost:8000/api/v1/reports \
  -H "Authorization: Bearer $token" \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "daily_power_forecast",
    "wind_farm_id": "farm-001",
    "date_range": {
      "start_date": "2024-01-01",
      "end_date": "2024-01-07"
    }
  }'
```

## Support and Maintenance

### Regular Maintenance Tasks
1. Monitor service health
2. Review access logs
3. Update SSL certificates
4. Clean up old data
5. Performance optimization

### Update Procedures
1. Backup current configuration
2. Test updates in staging
3. Deploy updates gradually
4. Monitor for issues
5. Rollback if necessary

For additional support, refer to:
- Kong Documentation: https://docs.konghq.com/
- Kong Community: https://discuss.konghq.com/
- GitHub Issues: https://github.com/Kong/kong/issues