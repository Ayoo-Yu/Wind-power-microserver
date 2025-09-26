#!/bin/bash

# Kong API Gateway Initialization Script
# This script initializes Kong with the required configuration

set -e

echo "🚀 Starting Kong API Gateway initialization..."

# Wait for Kong to be ready
echo "⏳ Waiting for Kong to be ready..."
until curl -s http://kong:8001/status | grep -q '"database":{"reachable":true'; do
    echo "  Waiting for Kong database connection..."
    sleep 5
done

echo "✅ Kong is ready!"

# Function to check if a service exists
service_exists() {
    local service_name=$1
    curl -s http://kong:8001/services/$service_name | grep -q '"name":"'$service_name'"'
}

# Function to check if a route exists
route_exists() {
    local route_name=$1
    curl -s http://kong:8001/routes/$route_name | grep -q '"name":"'$route_name'"'
}

# Function to create or update a service
create_service() {
    local name=$1
    local url=$2

    if service_exists $name; then
        echo "🔄 Updating service: $name"
        curl -s -X PATCH http://kong:8001/services/$name \
            -H "Content-Type: application/json" \
            -d "{\"url\":\"$url\"}" > /dev/null
    else
        echo "➕ Creating service: $name"
        curl -s -X POST http://kong:8001/services/ \
            -H "Content-Type: application/json" \
            -d "{\"name\":\"$name\",\"url\":\"$url\"}" > /dev/null
    fi
}

# Function to create or update a route
create_route() {
    local name=$1
    local service=$2
    local paths=$3
    local methods=$4

    if route_exists $name; then
        echo "🔄 Updating route: $name"
        curl -s -X PATCH http://kong:8001/routes/$name \
            -H "Content-Type: application/json" \
            -d "{\"paths\":[$paths],\"methods\":[$methods]}" > /dev/null
    else
        echo "➕ Creating route: $name"
        curl -s -X POST http://kong:8001/routes/ \
            -H "Content-Type: application/json" \
            -d "{\"name\":\"$name\",\"service\":{\"name\":\"$service\"},\"paths\":[$paths],\"methods\":[$methods],\"strip_path\":false}" > /dev/null
    fi
}

# Function to enable a plugin on a service
enable_plugin() {
    local service=$1
    local plugin=$2
    local config=$3

    echo "🔌 Enabling plugin: $plugin on service: $service"
    curl -s -X POST http://kong:8001/services/$service/plugins \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"$plugin\",\"config\":$config}" > /dev/null
}

# Function to create upstream
create_upstream() {
    local name=$1

    echo "🏗️  Creating upstream: $name"
    curl -s -X POST http://kong:8001/upstreams/ \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"$name\"}" > /dev/null
}

# Function to add target to upstream
add_target() {
    local upstream=$1
    local target=$2

    echo "🎯 Adding target: $target to upstream: $upstream"
    curl -s -X POST http://kong:8001/upstreams/$upstream/targets \
        -H "Content-Type: application/json" \
        -d "{\"target\":\"$target\",\"weight\":100}" > /dev/null
}

# Function to create consumer
create_consumer() {
    local username=$1
    local custom_id=$2

    echo "👤 Creating consumer: $username"
    curl -s -X POST http://kong:8001/consumers/ \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$username\",\"custom_id\":\"$custom_id\"}" > /dev/null
}

# Function to create JWT credential
create_jwt_credential() {
    local consumer=$1
    local key=$2
    local secret=$3

    echo "🔑 Creating JWT credential for consumer: $consumer"
    curl -s -X POST http://kong:8001/consumers/$consumer/jwt \
        -H "Content-Type: application/json" \
        -d "{\"key\":\"$key\",\"secret\":\"$secret\",\"algorithm\":\"HS256\"}" > /dev/null
}

# Create services
echo "🏗️  Creating services..."
create_service "meteorological-service" "http://meteorological-service:8001"
create_service "scada-service" "http://scada-service:8002"
create_service "power-prediction-service" "http://power-prediction-service:8003"
create_service "report-service" "http://report-service:8004"
create_service "tenant-service" "http://tenant-service:8007"
create_service "wind-farm-service" "http://windfarm-service:8006"

# Create routes for each service
echo "🛣️  Creating routes..."

# Meteorological Service Routes
create_route "weather-stations" "meteorological-service" '"/api/v1/weather-stations"' '["GET","POST","PUT","DELETE"]'
create_route "weather-data" "meteorological-service" '"/api/v1/weather-data"' '["GET","POST"]'
create_route "forecasts" "meteorological-service" '"/api/v1/forecasts"' '["GET","POST"]'
create_route "meteorological-health" "meteorological-service" '"/health"' '["GET"]'

# SCADA Service Routes
create_route "scada-data" "scada-service" '"/api/v1/scada-data"' '["GET","POST"]'
create_route "scada-alerts" "scada-service" '"/api/v1/scada-alerts"' '["GET","POST","PUT","DELETE"]'
create_route "scada-health" "scada-service" '"/health"' '["GET"]'

# Power Prediction Service Routes
create_route "predictions" "power-prediction-service" '"/api/v1/predictions"' '["GET","POST"]'
create_route "ml-models" "power-prediction-service" '"/api/v1/ml-models"' '["GET","POST","PUT","DELETE"]'
create_route "prediction-health" "power-prediction-service" '"/health"' '["GET"]'

# Report Service Routes
create_route "reports" "report-service" '"/api/v1/reports"' '["GET","POST","PUT","DELETE"]'
create_route "charts" "report-service" '"/api/v1/charts"' '["GET","POST","DELETE"]'
create_route "templates" "report-service" '"/api/v1/templates"' '["GET","POST","PUT","DELETE"]'
create_route "report-health" "report-service" '"/health"' '["GET"]'

# Tenant Service Routes
create_route "auth" "tenant-service" '"/api/v1/auth"' '["POST"]'
create_route "users" "tenant-service" '"/api/v1/users"' '["GET","POST","PUT","DELETE"]'
create_route "tenants" "tenant-service" '"/api/v1/tenants"' '["GET","POST","PUT","DELETE"]'
create_route "tenant-health" "tenant-service" '"/health"' '["GET"]'

# Wind Farm Service Routes
create_route "wind-farms" "wind-farm-service" '"/api/v1/wind-farms"' '["GET","POST","PUT","DELETE"]'
create_route "turbines" "wind-farm-service" '"/api/v1/turbines"' '["GET","POST","PUT","DELETE"]'
create_route "wind-farm-health" "wind-farm-service" '"/health"' '["GET"]'

# Enable global plugins
echo "🔌 Enabling global plugins..."

# CORS Plugin
curl -s -X POST http://kong:8001/plugins \
    -H "Content-Type: application/json" \
    -d '{
        "name": "cors",
        "config": {
            "origins": ["http://localhost:3000", "http://localhost:8080", "http://localhost:8000"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "headers": ["Accept", "Accept-Version", "Content-Length", "Content-MD5", "Content-Type", "Date", "Authorization", "Access-Control-Allow-Origin", "X-Requested-With"],
            "exposed_headers": ["X-Auth-Token"],
            "credentials": true,
            "max_age": 3600
        }
    }' > /dev/null

# Rate Limiting Plugin
curl -s -X POST http://kong:8001/plugins \
    -H "Content-Type: application/json" \
    -d '{
        "name": "rate-limiting",
        "config": {
            "minute": 1000,
            "hour": 10000,
            "day": 100000,
            "limit_by": "consumer",
            "policy": "local"
        }
    }' > /dev/null

# Prometheus Plugin
curl -s -X POST http://kong:8001/plugins \
    -H "Content-Type: application/json" \
    -d '{
        "name": "prometheus",
        "config": {
            "per_consumer": true,
            "status_code_metrics": true,
            "latency_metrics": true,
            "bandwidth_metrics": true,
            "upstream_health_metrics": true
        }
    }' > /dev/null

# Request Transformer Plugin
curl -s -X POST http://kong:8001/plugins \
    -H "Content-Type: application/json" \
    -d '{
        "name": "request-transformer",
        "config": {
            "add": {
                "headers": ["X-Kong-Proxy:true", "X-Kong-Version:3.5.0"]
            },
            "remove": {
                "headers": ["Server", "X-Powered-By"]
            }
        }
    }' > /dev/null

# Create consumers for different clients
echo "👤 Creating consumers..."
create_consumer "wind-farm-web-ui" "wind-farm-web-ui-001"
create_consumer "wind-farm-mobile-app" "wind-farm-mobile-app-001"
create_consumer "external-api-client" "external-api-client-001"
create_consumer "admin-client" "admin-client-001"

# Create JWT credentials for consumers
echo "🔑 Creating JWT credentials..."
create_jwt_credential "wind-farm-web-ui" "wind-farm-web-ui-key" "wind-farm-web-ui-secret-key-change-in-production"
create_jwt_credential "wind-farm-mobile-app" "wind-farm-mobile-app-key" "wind-farm-mobile-app-secret-key-change-in-production"
create_jwt_credential "external-api-client" "external-api-client-key" "external-api-client-secret-key-change-in-production"
create_jwt_credential "admin-client" "admin-client-key" "admin-client-secret-key-change-in-production"

echo "✅ Kong API Gateway initialization completed successfully!"
echo ""
echo "🔗 API Gateway URLs:"
echo "   Proxy: http://localhost:8000"
echo "   Admin API: http://localhost:8001"
echo "   Admin GUI: http://localhost:8002"
echo "   Konga GUI: http://localhost:1337"
echo ""
echo "📊 Available Services:"
echo "   Meteorological Service: /api/v1/weather-*"
echo "   SCADA Service: /api/v1/scada-*"
echo "   Power Prediction Service: /api/v1/predictions, /api/v1/ml-models"
echo "   Report Service: /api/v1/reports, /api/v1/charts, /api/v1/templates"
echo "   Tenant Service: /api/v1/auth, /api/v1/users, /api/v1/tenants"
echo "   Wind Farm Service: /api/v1/wind-farms, /api/v1/turbines"
echo ""
echo "🔐 JWT Authentication:"
echo "   Use the generated keys to authenticate API requests"
echo "   Add Authorization header: Bearer <your-jwt-token>"
echo ""
echo "📈 Monitoring:"
echo "   Prometheus metrics: http://localhost:8001/metrics"
echo "   Health checks: http://localhost:8000/health/*"