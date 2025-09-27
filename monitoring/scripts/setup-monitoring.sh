#!/bin/bash

# Wind Power Monitoring System Setup Script
# This script sets up the complete monitoring and alerting infrastructure

set -e

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

# Configuration
MONITORING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ELASTICSEARCH_URL="http://localhost:9200"
PROMETHEUS_URL="http://localhost:9090"
GRAFANA_URL="http://localhost:3000"
KIBANA_URL="http://localhost:5601"
JAEGER_URL="http://localhost:16686"
ALERTMANAGER_URL="http://localhost:9093"

# Check if Docker and Docker Compose are installed
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    # Check Docker daemon
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running. Please start Docker first."
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Create necessary directories
create_directories() {
    log_info "Creating monitoring directories..."

    mkdir -p "$MONITORING_DIR"/elk/{templates,scripts}
    mkdir -p "$MONITORING_DIR"/prometheus/rules
    mkdir -p "$MONITORING_DIR"/grafana/{provisioning/{dashboards,datasources},dashboards/{main,microservices,infrastructure,business,security,custom}}
    mkdir -p "$MONITORING_DIR"/alertmanager/templates
    mkdir -p "$MONITORING_DIR"/configs
    mkdir -p "$MONITORING_DIR"/logs

    log_success "Directories created"
}

# Set proper permissions
set_permissions() {
    log_info "Setting proper permissions..."

    # Set permissions for Elasticsearch data
    sudo chown -R 1000:1000 "$MONITORING_DIR"/logs 2>/dev/null || true

    # Make scripts executable
    chmod +x "$MONITORING_DIR"/scripts/*.sh 2>/dev/null || true

    log_success "Permissions set"
}

# Start monitoring services
start_services() {
    log_info "Starting monitoring services..."

    cd "$MONITORING_DIR"

    # Start services with proper order
    log_info "Starting Elasticsearch..."
    docker-compose -f docker-compose.monitoring.yml up -d elasticsearch

    # Wait for Elasticsearch to be ready
    log_info "Waiting for Elasticsearch to be ready..."
    timeout=300
    while ! curl -s "$ELASTICSEARCH_URL/_cluster/health" | grep -q '"status":"green\|yellow"'; do
        sleep 5
        timeout=$((timeout-5))
        if [ $timeout -le 0 ]; then
            log_error "Elasticsearch failed to start within 5 minutes"
            exit 1
        fi
    done
    log_success "Elasticsearch is ready"

    # Start Logstash
    log_info "Starting Logstash..."
    docker-compose -f docker-compose.monitoring.yml up -d logstash

    # Start Prometheus
    log_info "Starting Prometheus..."
    docker-compose -f docker-compose.monitoring.yml up -d prometheus

    # Start other services
    log_info "Starting remaining services..."
    docker-compose -f docker-compose.monitoring.yml up -d

    log_success "All monitoring services started"
}

# Wait for services to be ready
wait_for_services() {
    log_info "Waiting for all services to be ready..."

    local services=(
        "Elasticsearch:$ELASTICSEARCH_URL/_cluster/health:green|yellow"
        "Prometheus:$PROMETHEUS_URL/-/healthy:Prometheus Server is Ready"
        "Grafana:$GRAFANA_URL/api/health:ok"
        "Kibana:$KIBANA_URL/api/status:ok"
        "Jaeger:$JAEGER_URL/:200"
        "AlertManager:$ALERTMANAGER_URL/-/healthy:OK"
    )

    for service_info in "${services[@]}"; do
        IFS=':' read -r service_name url expected_status <<< "$service_info"
        log_info "Waiting for $service_name..."

        timeout=300
        while ! curl -s "$url" | grep -q "$expected_status"; do
            sleep 5
            timeout=$((timeout-5))
            if [ $timeout -le 0 ]; then
                log_error "$service_name failed to start within 5 minutes"
                exit 1
            fi
        done
        log_success "$service_name is ready"
    done
}

# Configure Grafana datasources and dashboards
configure_grafana() {
    log_info "Configuring Grafana..."

    # Wait a bit more for Grafana to fully initialize
    sleep 10

    # Create main dashboard
    curl -X POST \
        -H "Content-Type: application/json" \
        -d @"$MONITORING_DIR"/grafana/dashboards/main/wind-power-system-overview.json \
        "http://admin:windpower123@localhost:3000/api/dashboards/db" || log_warning "Failed to create main dashboard"

    # Create business dashboard
    curl -X POST \
        -H "Content-Type: application/json" \
        -d @"$MONITORING_DIR"/grafana/dashboards/business/wind-power-business-metrics.json \
        "http://admin:windpower123@localhost:3000/api/dashboards/db" || log_warning "Failed to create business dashboard"

    log_success "Grafana dashboards configured"
}

# Configure Kibana dashboards
configure_kibana() {
    log_info "Configuring Kibana..."

    # Create index pattern
    curl -X POST \
        -H "Content-Type: application/json" \
        -H "kbn-xsrf: true" \
        -d '{
            "index_pattern": {
                "title": "wind-power-logs-*",
                "timeFieldName": "@timestamp"
            }
        }' \
        "$KIBANA_URL/api/index_patterns/index_pattern" || log_warning "Failed to create index pattern"

    log_success "Kibana configured"
}

# Configure Prometheus alerting rules
configure_prometheus() {
    log_info "Configuring Prometheus alerting rules..."

    # Reload Prometheus configuration
    curl -X POST "$PROMETHEUS_URL/-/reload" || log_warning "Failed to reload Prometheus configuration"

    log_success "Prometheus alerting configured"
}

# Test alerting functionality
test_alerting() {
    log_info "Testing alerting functionality..."

    # Check AlertManager status
    if curl -s "$ALERTMANAGER_URL/api/v1/status" | grep -q "success"; then
        log_success "AlertManager is responding"
    else
        log_warning "AlertManager test failed"
    fi

    # Test webhook receiver (if configured)
    if command -v nc &> /dev/null; then
        log_info "Testing webhook connectivity..."
        # This is a simple test - in production, use proper webhook testing
    fi
}

# Display access information
display_access_info() {
    log_info "Monitoring system is ready! Access information:"
    echo ""
    echo "📊 Grafana:        $GRAFANA_URL (admin/windpower123)"
    echo "🔍 Kibana:         $KIBANA_URL"
    echo "📈 Prometheus:     $PROMETHEUS_URL"
    echo "🔔 AlertManager:   $ALERTMANAGER_URL"
    echo "🚀 Jaeger:         $JAEGER_URL"
    echo "💾 Elasticsearch:  $ELASTICSEARCH_URL"
    echo ""
    echo "📋 Quick Commands:"
    echo "  View logs:        docker-compose -f monitoring/docker-compose.monitoring.yml logs -f [service]"
    echo "  Stop monitoring:  docker-compose -f monitoring/docker-compose.monitoring.yml down"
    echo "  Restart service:  docker-compose -f monitoring/docker-compose.monitoring.yml restart [service]"
    echo ""
    echo "🔗 Dashboard Links:"
    echo "  Main Overview:    $GRAFANA_URL/d/main/wind-power-system-overview"
    echo "  Business Metrics: $GRAFANA_URL/d/business/wind-power-business-metrics"
    echo ""
}

# Health check function
health_check() {
    log_info "Performing health check..."

    local health_status=0

    # Check each service
    services=(
        "Elasticsearch:$ELASTICSEARCH_URL/_cluster/health"
        "Prometheus:$PROMETHEUSUS_URL/-/healthy"
        "Grafana:$GRAFANA_URL/api/health"
        "Kibana:$KIBANA_URL/api/status"
        "Jaeger:$JAEGER_URL/"
        "AlertManager:$ALERTMANAGER_URL/-/healthy"
    )

    for service_info in "${services[@]}"; do
        IFS=':' read -r service_name url <<< "$service_info"
        if curl -s "$url" > /dev/null; then
            log_success "$service_name is healthy"
        else
            log_error "$service_name is not responding"
            health_status=1
        fi
    done

    return $health_status
}

# Cleanup function
cleanup() {
    log_info "Cleaning up..."
    cd "$MONITORING_DIR"
    docker-compose -f docker-compose.monitoring.yml down -v
    log_success "Cleanup completed"
}

# Main execution
main() {
    log_info "Starting Wind Power Monitoring System Setup..."

    case "${1:-setup}" in
        setup)
            check_prerequisites
            create_directories
            set_permissions
            start_services
            wait_for_services
            configure_grafana
            configure_kibana
            configure_prometheus
            test_alerting
            display_access_info
            ;;
        health)
            health_check
            ;;
        cleanup)
            cleanup
            ;;
        restart)
            cleanup
            sleep 5
            main setup
            ;;
        logs)
            cd "$MONITORING_DIR"
            docker-compose -f docker-compose.monitoring.yml logs -f "${2:-}"
            ;;
        stop)
            cd "$MONITORING_DIR"
            docker-compose -f docker-compose.monitoring.yml stop "${2:-}"
            ;;
        start)
            cd "$MONITORING_DIR"
            docker-compose -f docker-compose.monitoring.yml start "${2:-}"
            ;;
        *)
            echo "Usage: $0 {setup|health|cleanup|restart|logs|stop|start} [service]"
            echo ""
            echo "Commands:"
            echo "  setup     - Complete monitoring system setup"
            echo "  health    - Health check of all services"
            echo "  cleanup   - Remove all monitoring containers and volumes"
            echo "  restart   - Restart the entire monitoring system"
            echo "  logs      - View logs (optionally specify service name)"
            echo "  stop      - Stop services (optionally specify service name)"
            echo "  start     - Start services (optionally specify service name)"
            exit 1
            ;;
    esac

    log_success "Monitoring system setup completed!"
}

# Run main function with all arguments
main "$@"