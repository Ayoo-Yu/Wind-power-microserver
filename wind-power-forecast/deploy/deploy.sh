#!/bin/bash
set -e

# =============================================================
# Wind Power Forecast - Deployment Script
# Usage: ./deploy.sh [command]
#   ./deploy.sh install   - Load images and create network
#   ./deploy.sh start     - Start all services
#   ./deploy.sh stop      - Stop all services
#   ./deploy.sh status    - Show service status
#   ./deploy.sh restart   - Restart all services
#   ./deploy.sh db-only   - Start only the database
#   ./deploy.sh logs      - Tail logs from all services
# =============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

check_env() {
    if [ ! -f .env ]; then
        error ".env file not found!"
        info "Copy .env.example to .env and modify values:"
        info "  cp .env.example .env"
        info "  vi .env"
        exit 1
    fi
    # Source .env for variable access
    set -a
    source .env
    set +a
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed!"
        exit 1
    fi
    if ! docker info &> /dev/null; then
        error "Docker daemon is not running!"
        exit 1
    fi
    if ! command -v docker &> /dev/null && docker compose version &> /dev/null; then
        error "Docker Compose V2 is not available!"
        exit 1
    fi
}

create_network() {
    if ! docker network inspect wind-power-network &> /dev/null; then
        info "Creating Docker network: wind-power-network"
        docker network create wind-power-network
    fi
}

create_dirs() {
    info "Creating data directories..."
    mkdir -p datasets predict_inputs models predict_outputs logs_middle
    mkdir -p merged_predict_outputs feature_importance_mid
    mkdir -p datasets_short predict_inputs_short models_short predict_outputs_short
    mkdir -p logs_short feature_importance_short
    mkdir -p datasets_ss saved_models_ss prediction_inputs_ss prediction_results_ss logs_ss
}

do_install() {
    info "=== Installing Wind Power Forecast System ==="
    check_docker

    # Load database image
    if [ -f ../01_database.tar ]; then
        info "Loading database image..."
        docker load -i ../01_database.tar
    else
        warn "01_database.tar not found, skipping database image"
    fi

    # Load prediction system image
    if [ -f ../02_prediction_system.tar ]; then
        info "Loading prediction system images..."
        docker load -i ../02_prediction_system.tar
    else
        warn "02_prediction_system.tar not found, skipping prediction system images"
    fi

    create_network
    create_dirs

    info "=== Installation complete ==="
    info "Next steps:"
    info "  1. cp .env.example .env && vi .env"
    info "  2. ./deploy.sh start"
}

do_start() {
    check_env
    check_docker
    create_network
    create_dirs

    info "Starting database..."
    docker compose -f docker-compose.db.yaml up -d

    info "Waiting for database to be ready..."
    for i in $(seq 1 30); do
        if docker exec wind-power-kingbase ls /home/kingbase/userdata/data &> /dev/null; then
            info "Database is ready."
            break
        fi
        if [ $i -eq 30 ]; then
            warn "Database health check timeout, continuing anyway..."
        fi
        sleep 2
    done

    info "Starting prediction system..."
    docker compose -f docker-compose.prod.yaml up -d

    info "=== All services started ==="
    info "Frontend:    http://<server-ip>:8080"
    info "Backend API: http://<server-ip>:5000"
    info "pgAdmin:     http://<server-ip>:5050"
}

do_stop() {
    info "Stopping prediction system..."
    docker compose -f docker-compose.prod.yaml down 2>/dev/null || true

    info "Stopping database..."
    docker compose -f docker-compose.db.yaml down 2>/dev/null || true

    info "All services stopped."
}

do_status() {
    echo ""
    echo "=== Database ==="
    docker compose -f docker-compose.db.yaml ps 2>/dev/null || echo "  Not started"
    echo ""
    echo "=== Prediction System ==="
    docker compose -f docker-compose.prod.yaml ps 2>/dev/null || echo "  Not started"
    echo ""
}

do_restart() {
    info "Restarting all services..."
    do_stop
    sleep 3
    do_start
}

do_db_only() {
    check_env
    check_docker
    create_network

    info "Starting database only..."
    docker compose -f docker-compose.db.yaml up -d
    info "Database started on port 54321"
}

do_logs() {
    local svc="${1:-}"
    if [ -n "$svc" ]; then
        docker compose -f docker-compose.prod.yaml logs -f "$svc" 2>/dev/null || \
        docker compose -f docker-compose.db.yaml logs -f "$svc"
    else
        docker compose -f docker-compose.prod.yaml logs -f 2>/dev/null &
        docker compose -f docker-compose.db.yaml logs -f 2>/dev/null &
        wait
    fi
}

case "${1:-}" in
    install)  do_install  ;;
    start)    do_start    ;;
    stop)     do_stop     ;;
    status)   do_status   ;;
    restart)  do_restart  ;;
    db-only)  do_db_only  ;;
    logs)     do_logs "${2:-}" ;;
    *)
        echo "Usage: $0 {install|start|stop|status|restart|db-only|logs [service]}"
        echo ""
        echo "Commands:"
        echo "  install   Load Docker images from tar files"
        echo "  start     Start all services (DB first, then app)"
        echo "  stop      Stop all services"
        echo "  status    Show status of all services"
        echo "  restart   Restart all services"
        echo "  db-only   Start only the database"
        echo "  logs      Tail logs (optional: specify service name)"
        exit 1
        ;;
esac
