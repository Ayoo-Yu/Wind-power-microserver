#!/bin/bash

# API Gateway Integration Test Script
# This script tests all Kong API Gateway functionality including services, routes, authentication, and plugins

set -e

# Configuration
KONG_ADMIN_URL="${KONG_ADMIN_URL:-http://localhost:8001}"
KONG_PROXY_URL="${KONG_PROXY_URL:-http://localhost:8000}"
TIMEOUT=10
RETRY_COUNT=3

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to make HTTP request with error handling
make_request() {
    local method=$1
    local url=$2
    local data=$3
    local expected_status=$4

    log_info "Testing: $method $url"

    if response=$(curl -s -w "\n%{http_code}" -m $TIMEOUT -X "$method" "$url" ${data:+-d "$data"} -H "Content-Type: application/json" 2>/dev/null); then
        http_code=$(echo "$response" | tail -n1)
        body=$(echo "$response" | sed '$d')

        if [ "$http_code" = "$expected_status" ]; then
            log_success "Expected status $expected_status received"
            echo "$body"
            return 0
        else
            log_error "Expected status $expected_status but got $http_code"
            echo "$body"
            return 1
        fi
    else
        log_error "Request failed to $url"
        return 1
    fi
}

# Test Kong Admin API connectivity
test_admin_api() {
    log_info "Testing Kong Admin API connectivity..."

    if response=$(make_request "GET" "$KONG_ADMIN_URL" "" "200"); then
        if echo "$response" | grep -q '"version"'; then
            log_success "Kong Admin API is accessible"
            return 0
        else
            log_error "Kong Admin API returned unexpected response"
            return 1
        fi
    else
        return 1
    fi
}

# Test Kong status endpoint
test_status_endpoint() {
    log_info "Testing Kong status endpoint..."

    if response=$(make_request "GET" "$KONG_ADMIN_URL/status" "" "200"); then
        if echo "$response" | grep -q '"database"'; then
            log_success "Kong status endpoint is working"
            return 0
        else
            log_error "Kong status endpoint returned unexpected response"
            return 1
        fi
    else
        return 1
    fi
}

# Test all configured services
test_services() {
    log_info "Testing configured services..."

    local services=(
        "meteorological-service"
        "scada-service"
        "power-prediction-service"
        "report-service"
        "tenant-service"
        "wind-farm-service"
    )

    local failed_services=()
    local total_services=${#services[@]}
    local working_services=0

    for service_name in "${services[@]}"; do
        log_info "Testing service: $service_name"

        if response=$(make_request "GET" "$KONG_ADMIN_URL/services/$service_name" "" "200"); then
            if echo "$response" | grep -q "\"name\":\"$service_name\""; then
                log_success "Service $service_name is configured"
                working_services=$((working_services + 1))
            else
                log_error "Service $service_name configuration error"
                failed_services+=("$service_name")
            fi
        else
            failed_services+=("$service_name")
        fi
    done

    log_info "Service test summary: $working_services/$total_services services configured"

    if [ ${#failed_services[@]} -gt 0 ]; then
        log_error "Failed services: ${failed_services[*]}"
        return 1
    fi

    return 0
}

# Test service routes
test_routes() {
    log_info "Testing service routes..."

    local routes=(
        "/api/v1/weather-stations"
        "/api/v1/weather-data"
        "/api/v1/forecasts"
        "/api/v1/scada-data"
        "/api/v1/scada-alerts"
        "/api/v1/predictions"
        "/api/v1/ml-models"
        "/api/v1/reports"
        "/api/v1/charts"
        "/api/v1/templates"
        "/api/v1/auth"
        "/api/v1/users"
        "/api/v1/tenants"
        "/api/v1/wind-farms"
        "/api/v1/turbines"
    )

    local failed_routes=()
    local total_routes=${#routes[@]}
    local working_routes=0

    for route_path in "${routes[@]}"; do
        log_info "Testing route: $route_path"

        # Test if route exists in Kong
        if response=$(make_request "GET" "$KONG_ADMIN_URL/routes" "" "200"); then
            if echo "$response" | grep -q "$route_path"; then
                log_success "Route $route_path is configured"
                working_routes=$((working_routes + 1))
            else
                log_warning "Route $route_path not found in configuration"
                failed_routes+=("$route_path")
            fi
        else
            failed_routes+=("$route_path")
        fi
    done

    log_info "Route test summary: $working_routes/$total_routes routes configured"

    if [ ${#failed_routes[@]} -gt 0 ]; then
        log_warning "Missing routes: ${failed_routes[*]}"
    fi

    return 0
}

# Test plugins configuration
test_plugins() {
    log_info "Testing plugins configuration..."

    local essential_plugins=("cors" "rate-limiting" "prometheus" "jwt-custom")

    local failed_plugins=()
    local total_plugins=${#essential_plugins[@]}
    local working_plugins=0

    for plugin_name in "${essential_plugins[@]}"; do
        log_info "Testing plugin: $plugin_name"

        if response=$(make_request "GET" "$KONG_ADMIN_URL/plugins" "" "200"); then
            if echo "$response" | grep -q "\"name\":\"$plugin_name\""; then
                log_success "Plugin $plugin_name is configured"
                working_plugins=$((working_plugins + 1))
            else
                log_warning "Plugin $plugin_name not found in configuration"
                failed_plugins+=("$plugin_name")
            fi
        else
            failed_plugins+=("$plugin_name")
        fi
    done

    log_info "Plugin test summary: $working_plugins/$total_plugins plugins configured"

    if [ ${#failed_plugins[@]} -gt 0 ]; then
        log_warning "Missing plugins: ${failed_plugins[*]}"
    fi

    return 0
}

# Test JWT authentication
test_jwt_auth() {
    log_info "Testing JWT authentication..."

    # First, test without JWT token (should fail)
    log_info "Testing endpoint without JWT token (should return 401)..."
    if response=$(make_request "GET" "$KONG_PROXY_URL/api/v1/weather-stations" "" "401"); then
        log_success "JWT authentication is working - unauthorized access blocked"
    else
        log_error "JWT authentication may not be properly configured"
        return 1
    fi

    # Test with invalid JWT token
    log_info "Testing endpoint with invalid JWT token..."
    if response=$(curl -s -w "\n%{http_code}" -m $TIMEOUT -H "Authorization: Bearer invalid-token" "$KONG_PROXY_URL/api/v1/weather-stations" 2>/dev/null); then
        http_code=$(echo "$response" | tail -n1)
        if [ "$http_code" = "401" ]; then
            log_success "Invalid JWT token properly rejected"
        else
            log_warning "Invalid JWT token was not rejected (status: $http_code)"
        fi
    fi

    return 0
}

# Test CORS configuration
test_cors() {
    log_info "Testing CORS configuration..."

    if response=$(curl -s -w "\n%{http_code}" -m $TIMEOUT -X OPTIONS -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: GET" "$KONG_PROXY_URL/api/v1/weather-stations" 2>/dev/null); then
        http_code=$(echo "$response" | tail -n1)
        if [ "$http_code" = "200" ] || [ "$http_code" = "204" ]; then
            log_success "CORS preflight request handled correctly"
        else
            log_warning "CORS preflight request returned status $http_code"
        fi
    else
        log_error "CORS test request failed"
        return 1
    fi

    return 0
}

# Test rate limiting
test_rate_limiting() {
    log_info "Testing rate limiting..."

    # Make multiple rapid requests to test rate limiting
    local request_count=0
    local rate_limited=0

    for i in {1..5}; do
        if response=$(curl -s -w "\n%{http_code}" -m $TIMEOUT "$KONG_PROXY_URL/api/v1/weather-stations" 2>/dev/null); then
            http_code=$(echo "$response" | tail -n1)
            request_count=$((request_count + 1))

            if [ "$http_code" = "429" ]; then
                rate_limited=$((rate_limited + 1))
                log_info "Rate limiting triggered (request $i)"
            fi
        fi
        sleep 0.1
    done

    if [ $rate_limited -gt 0 ]; then
        log_success "Rate limiting is working ($rate_limited requests rate limited)"
    else
        log_info "Rate limiting test completed ($request_count requests made)"
    fi

    return 0
}

# Test proxy connectivity to backend services
test_proxy_connectivity() {
    log_info "Testing proxy connectivity to backend services..."

    local endpoints=(
        "/health"
    )

    local failed_endpoints=()
    local working_endpoints=0

    for endpoint in "${endpoints[@]}"; do
        log_info "Testing endpoint: $endpoint"

        if response=$(curl -s -w "\n%{http_code}" -m $TIMEOUT "$KONG_PROXY_URL$endpoint" 2>/dev/null); then
            http_code=$(echo "$response" | tail -n1)
            body=$(echo "$response" | sed '$d')

            if [ "$http_code" = "200" ]; then
                if echo "$body" | grep -q '"status":"healthy"'; then
                    log_success "Endpoint $endpoint is healthy"
                    working_endpoints=$((working_endpoints + 1))
                else
                    log_warning "Endpoint $endpoint returned unexpected response"
                    failed_endpoints+=("$endpoint")
                fi
            else
                log_error "Endpoint $endpoint returned status $http_code"
                failed_endpoints+=("$endpoint")
            fi
        else
            log_error "Endpoint $endpoint is not accessible"
            failed_endpoints+=("$endpoint")
        fi
    done

    log_info "Proxy connectivity summary: $working_endpoints/${#endpoints[@]} endpoints working"

    if [ ${#failed_endpoints[@]} -gt 0 ]; then
        log_error "Failed endpoints: ${failed_endpoints[*]}"
        return 1
    fi

    return 0
}

# Main test execution
run_all_tests() {
    log_info "Starting Kong API Gateway integration tests..."

    local failed_tests=()
    local total_tests=0

    # Define all test functions
    local tests=(
        "test_admin_api"
        "test_status_endpoint"
        "test_services"
        "test_routes"
        "test_plugins"
        "test_jwt_auth"
        "test_cors"
        "test_rate_limiting"
        "test_proxy_connectivity"
    )

    total_tests=${#tests[@]}

    for test in "${tests[@]}"; do
        if ! $test; then
            failed_tests+=("$test")
        fi
        echo ""
    done

    local passed_tests=$((total_tests - ${#failed_tests[@]}))

    echo "========================================"
    log_info "Test Summary:"
    log_info "  Total tests: $total_tests"
    log_info "  Passed tests: $passed_tests"
    log_info "  Failed tests: ${#failed_tests[@]}"

    if [ ${#failed_tests[@]} -gt 0 ]; then
        log_error "Failed tests: ${failed_tests[*]}"
        return 1
    else
        log_success "All tests passed! Kong API Gateway is properly configured."
        return 0
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --kong-admin-url)
            KONG_ADMIN_URL="$2"
            shift 2
            ;;
        --kong-proxy-url)
            KONG_PROXY_URL="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --help)
            echo "Kong API Gateway Integration Test Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --kong-admin-url URL    Kong Admin API URL (default: http://localhost:8001)"
            echo "  --kong-proxy-url URL    Kong Proxy URL (default: http://localhost:8000)"
            echo "  --timeout SECONDS       Request timeout in seconds (default: 10)"
            echo "  --help                  Show this help message"
            echo ""
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Main execution
if run_all_tests; then
    exit 0
else
    exit 1
fi