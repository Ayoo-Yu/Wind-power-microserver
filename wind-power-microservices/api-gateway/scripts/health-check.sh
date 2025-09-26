#!/bin/bash

# Kong API Gateway Health Check Script
# This script performs comprehensive health checks on Kong and all services

set -e

# Configuration
KONG_ADMIN_URL="${KONG_ADMIN_URL:-http://localhost:8001}"
KONG_PROXY_URL="${KONG_PROXY_URL:-http://localhost:8000}"
TIMEOUT=10
RETRY_COUNT=3
RETRY_DELAY=5

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

# Function to make HTTP request with retries
make_request() {
    local method=$1
    local url=$2
    local max_retries=$3
    local current_retry=0

    while [ $current_retry -lt $max_retries ]; do
        if response=$(curl -s -w "\n%{http_code}" -m $TIMEOUT -X "$method" "$url" 2>/dev/null); then
            http_code=$(echo "$response" | tail -n1)
            body=$(echo "$response" | sed '$d')

            if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
                echo "$body"
                return 0
            else
                log_warning "HTTP $http_code from $url (attempt $((current_retry + 1))/$max_retries)"
            fi
        else
            log_warning "Request failed to $url (attempt $((current_retry + 1))/$max_retries)"
        fi

        current_retry=$((current_retry + 1))
        if [ $current_retry -lt $max_retries ]; then
            sleep $RETRY_DELAY
        fi
    done

    log_error "All retry attempts failed for $url"
    return 1
}

# Function to check Kong server status
check_kong_status() {
    log_info "Checking Kong server status..."

    if response=$(make_request "GET" "$KONG_ADMIN_URL/status" $RETRY_COUNT); then
        if echo "$response" | grep -q '"database":{"reachable":true'; then
            log_success "Kong server is running and database is reachable"
            return 0
        else
            log_error "Kong server is running but database is not reachable"
            return 1
        fi
    else
        log_error "Kong server is not responding"
        return 1
    fi
}

# Function to check Kong health endpoint
check_kong_health() {
    log_info "Checking Kong health endpoint..."

    if response=$(make_request "GET" "$KONG_PROXY_URL/health" $RETRY_COUNT); then
        if echo "$response" | grep -q '"status":"healthy"'; then
            log_success "Kong health check passed"
            return 0
        else
            log_error "Kong health check failed"
            return 1
        fi
    else
        log_error "Kong health endpoint is not responding"
        return 1
    fi
}

# Function to check individual service
check_service() {
    local service_name=$1
    local service_path=$2

    log_info "Checking $service_name service..."

    if response=$(make_request "GET" "$KONG_PROXY_URL$service_path" $RETRY_COUNT); then
        if echo "$response" | grep -q '"status":"healthy"'; then
            log_success "$service_name service is healthy"
            return 0
        else
            log_warning "$service_name service returned unexpected response"
            return 1
        fi
    else
        log_error "$service_name service is not responding"
        return 1
    fi
}

# Function to check all services
check_all_services() {
    log_info "Checking all microservices..."

    local services=(
        "meteorological-service:/health"
        "scada-service:/health"
        "power-prediction-service:/health"
        "report-service:/health"
        "tenant-service:/health"
        "wind-farm-service:/health"
    )

    local failed_services=()
    local total_services=${#services[@]}
    local healthy_services=0

    for service in "${services[@]}"; do
        IFS=':' read -r service_name service_path <<< "$service"

        if check_service "$service_name" "$service_path"; then
            healthy_services=$((healthy_services + 1))
        else
            failed_services+=("$service_name")
        fi
    done

    log_info "Service health summary: $healthy_services/$total_services services are healthy"

    if [ ${#failed_services[@]} -gt 0 ]; then
        log_error "Failed services: ${failed_services[*]}"
        return 1
    fi

    return 0
}

# Function to check Kong plugins
check_plugins() {
    log_info "Checking Kong plugins..."

    if response=$(make_request "GET" "$KONG_ADMIN_URL/plugins" $RETRY_COUNT); then
        local plugin_count=$(echo "$response" | jq -r '.data | length' 2>/dev/null || echo "0")

        if [ "$plugin_count" -gt 0 ]; then
            log_success "Kong has $plugin_count plugins configured"

            # Check for essential plugins
            local essential_plugins=("cors" "rate-limiting" "prometheus")
            for plugin in "${essential_plugins[@]}"; do
                if echo "$response" | grep -q "\"name\":\"$plugin\""; then
                    log_success "Essential plugin '$plugin' is configured"
                else
                    log_warning "Essential plugin '$plugin' is not configured"
                fi
            done

            return 0
        else
            log_warning "No plugins are configured"
            return 1
        fi
    else
        log_error "Failed to retrieve plugins information"
        return 1
    fi
}

# Function to check Kong services
check_kong_services() {
    log_info "Checking Kong services..."

    if response=$(make_request "GET" "$KONG_ADMIN_URL/services" $RETRY_COUNT); then
        local service_count=$(echo "$response" | jq -r '.data | length' 2>/dev/null || echo "0")

        if [ "$service_count" -gt 0 ]; then
            log_success "Kong has $service_count services configured"

            # List configured services
            echo "$response" | jq -r '.data[].name' 2>/dev/null | while read -r service_name; do
                log_info "  - Service: $service_name"
            done

            return 0
        else
            log_warning "No services are configured"
            return 1
        fi
    else
        log_error "Failed to retrieve services information"
        return 1
    fi
}

# Function to check Kong routes
check_kong_routes() {
    log_info "Checking Kong routes..."

    if response=$(make_request "GET" "$KONG_ADMIN_URL/routes" $RETRY_COUNT); then
        local route_count=$(echo "$response" | jq -r '.data | length' 2>/dev/null || echo "0")

        if [ "$route_count" -gt 0 ]; then
            log_success "Kong has $route_count routes configured"
            return 0
        else
            log_warning "No routes are configured"
            return 1
        fi
    else
        log_error "Failed to retrieve routes information"
        return 1
    fi
}

# Function to check Kong consumers
check_kong_consumers() {
    log_info "Checking Kong consumers..."

    if response=$(make_request "GET" "$KONG_ADMIN_URL/consumers" $RETRY_COUNT); then
        local consumer_count=$(echo "$response" | jq -r '.data | length' 2>/dev/null || echo "0")

        if [ "$consumer_count" -gt 0 ]; then
            log_success "Kong has $consumer_count consumers configured"

            # Check for JWT credentials
            echo "$response" | jq -r '.data[].username' 2>/dev/null | while read -r username; do
                if jwt_response=$(make_request "GET" "$KONG_ADMIN_URL/consumers/$username/jwt" 1); then
                    local jwt_count=$(echo "$jwt_response" | jq -r '.data | length' 2>/dev/null || echo "0")
                    if [ "$jwt_count" -gt 0 ]; then
                        log_success "  - Consumer $username has JWT credentials"
                    else
                        log_warning "  - Consumer $username has no JWT credentials"
                    fi
                fi
            done

            return 0
        else
            log_warning "No consumers are configured"
            return 1
        fi
    else
        log_error "Failed to retrieve consumers information"
        return 1
    fi
}

# Function to check Kong upstreams
check_kong_upstreams() {
    log_info "Checking Kong upstreams..."

    if response=$(make_request "GET" "$KONG_ADMIN_URL/upstreams" $RETRY_COUNT); then
        local upstream_count=$(echo "$response" | jq -r '.data | length' 2>/dev/null || echo "0")

        if [ "$upstream_count" -gt 0 ]; then
            log_success "Kong has $upstream_count upstreams configured"
            return 0
        else
            log_info "No upstreams are configured (services using direct URLs)"
            return 0
        fi
    else
        log_error "Failed to retrieve upstreams information"
        return 1
    fi
}

# Function to check network connectivity
check_network_connectivity() {
    log_info "Checking network connectivity..."

    # Check if Kong ports are accessible
    if nc -z localhost 8000 2>/dev/null; then
        log_success "Kong proxy port (8000) is accessible"
    else
        log_error "Kong proxy port (8000) is not accessible"
        return 1
    fi

    if nc -z localhost 8001 2>/dev/null; then
        log_success "Kong admin port (8001) is accessible"
    else
        log_error "Kong admin port (8001) is not accessible"
        return 1
    fi

    return 0
}

# Function to perform comprehensive health check
comprehensive_health_check() {
    log_info "Starting comprehensive Kong API Gateway health check..."

    local failed_checks=()
    local total_checks=0

    # Define all check functions
    local checks=(
        "check_network_connectivity"
        "check_kong_status"
        "check_kong_health"
        "check_kong_services"
        "check_kong_routes"
        "check_kong_plugins"
        "check_kong_consumers"
        "check_kong_upstreams"
        "check_all_services"
    )

    total_checks=${#checks[@]}

    for check in "${checks[@]}"; do
        if ! $check; then
            failed_checks+=("$check")
        fi
    done

    local passed_checks=$((total_checks - ${#failed_checks[@]}))

    echo ""
    log_info "Health Check Summary:"
    log_info "  Total checks: $total_checks"
    log_info "  Passed checks: $passed_checks"
    log_info "  Failed checks: ${#failed_checks[@]}"

    if [ ${#failed_checks[@]} -gt 0 ]; then
        log_error "Failed checks: ${failed_checks[*]}"
        return 1
    else
        log_success "All health checks passed! Kong API Gateway is healthy and ready."
        return 0
    fi
}

# Function to display help
show_help() {
    echo "Kong API Gateway Health Check Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --kong-admin-url URL    Kong Admin API URL (default: http://localhost:8001)"
    echo "  --kong-proxy-url URL    Kong Proxy URL (default: http://localhost:8000)"
    echo "  --timeout SECONDS       Request timeout in seconds (default: 10)"
    echo "  --retry-count COUNT     Number of retry attempts (default: 3)"
    echo "  --retry-delay SECONDS   Delay between retries (default: 5)"
    echo "  --help                  Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run with default settings"
    echo "  $0 --kong-admin-url http://kong:8001  # Custom Kong admin URL"
    echo "  $0 --timeout 5 --retry-count 5        # Custom timeout and retries"
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
        --retry-count)
            RETRY_COUNT="$2"
            shift 2
            ;;
        --retry-delay)
            RETRY_DELAY="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
if comprehensive_health_check; then
    exit 0
else
    exit 1
fi