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

docker_compose() {
    # These environment variables are harmless on Linux, and avoid common
    # path-conversion surprises when this script is launched from Git Bash/MSYS.
    COMPOSE_IGNORE_ORPHANS=true \
    COMPOSE_CONVERT_WINDOWS_PATHS=1 \
    MSYS_NO_PATHCONV=1 \
    MSYS2_ARG_CONV_EXCL="*" \
    docker compose "$@"
}

is_wsl_windows_path() {
    [ -r /proc/version ] && grep -qi microsoft /proc/version && \
    [ "${SCRIPT_DIR#/mnt/}" != "$SCRIPT_DIR" ] && \
    command -v powershell.exe >/dev/null 2>&1 && \
    command -v wslpath >/dev/null 2>&1
}

host_mkdir() {
    local dir="$1"
    local wsl_dir
    local win_dir
    local ps_dir
    local ps_script
    local ps_encoded

    if is_wsl_windows_path; then
        wsl_dir="$(realpath -m "$dir")"
        win_dir="$(wslpath -w "$wsl_dir")"
        ps_dir="${win_dir//\'/\'\'}"
        ps_script="\$ProgressPreference = 'SilentlyContinue'; \$p = '$ps_dir'; if (Test-Path -LiteralPath \$p -PathType Leaf) { exit 2 }; New-Item -ItemType Directory -Force -Path \$p | Out-Null"
        ps_encoded="$(printf '%s' "$ps_script" | iconv -f UTF-8 -t UTF-16LE | base64 -w 0)"
        powershell.exe -NoProfile -NonInteractive -EncodedCommand "$ps_encoded" >/dev/null 2>&1
    else
        mkdir -p "$dir"
    fi
}

ensure_dir() {
    local dir
    for dir in "$@"; do
        if [ -e "$dir" ] && [ ! -d "$dir" ]; then
            error "Path exists but is not a directory: $dir"
            error "Please move or remove this file, then run: bash deploy.sh start"
            exit 1
        fi

        host_mkdir "$dir" || true

        if [ ! -d "$dir" ]; then
            error "Failed to create directory: $dir"
            error "Check filesystem permissions and Docker Desktop file sharing for: $SCRIPT_DIR"
            exit 1
        fi
    done
}

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
    if ! docker compose version &> /dev/null; then
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

generate_app_env() {
    cat > app.env <<EOF
DB_HOST=kingbase
DB_PORT=54321
DB_USER=system
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=windpower
SECRET_KEY=${SECRET_KEY}
JWT_SECRET_KEY=${SECRET_KEY}
APP_HOST=0.0.0.0
APP_PORT=5000
EOF
}

wait_for_database() {
    info "Waiting for database to be ready..."
    for i in $(seq 1 60); do
        if docker exec wind-power-kingbase \
            /home/kingbase/install/kingbase/bin/sys_isready \
            -h 127.0.0.1 -p 54321 >/dev/null 2>&1; then
            info "Database is ready."
            return 0
        fi

        if [ "$i" -eq 60 ]; then
            error "Database health check timeout."
            docker logs --tail 80 wind-power-kingbase 2>/dev/null || true
            exit 1
        fi

        sleep 2
    done
}

ensure_app_database() {
    local db_name="${DB_NAME:-windpower}"
    local db_user="${DB_USER:-system}"
    local ksql="/home/kingbase/install/kingbase/bin/ksql"
    local createdb="/home/kingbase/install/kingbase/bin/createdb"

    info "Ensuring database exists: $db_name"

    if docker exec --user kingbase wind-power-kingbase \
        "$ksql" -p 54321 -U "$db_user" -d "$db_name" -c "select 1;" >/dev/null 2>&1; then
        info "Database already exists: $db_name"
        return 0
    fi

    if docker exec --user kingbase wind-power-kingbase \
        "$createdb" -p 54321 -U "$db_user" "$db_name" >/dev/null 2>&1; then
        info "Created database: $db_name"
        return 0
    fi

    if docker exec --user kingbase wind-power-kingbase \
        "$ksql" -p 54321 -U "$db_user" -d "$db_name" -c "select 1;" >/dev/null 2>&1; then
        info "Database already exists: $db_name"
        return 0
    fi

    error "Failed to create or connect to database: $db_name"
    docker logs --tail 80 wind-power-kingbase 2>/dev/null || true
    exit 1
}

import_seed_data() {
    local db_name="${DB_NAME:-windpower}"
    local db_user="${DB_USER:-system}"
    local ksql="/home/kingbase/install/kingbase/bin/ksql"
    local dump_file="../03_seed_data.dump"

    # Check if data already exists (wind_farms table has rows)
    local count
    count=$(docker exec --user kingbase wind-power-kingbase \
        "$ksql" -p 54321 -U "$db_user" -d "$db_name" -t -A \
        -c "SELECT count(*) FROM wind_farms;" 2>/dev/null | tr -d '[:space:]')

    if [ "$count" != "0" ] && [ -n "$count" ]; then
        info "Database already has data ($count wind farms), skipping seed import."
        return 0
    fi

    if [ ! -f "$dump_file" ]; then
        warn "Seed data file not found: $dump_file"
        warn "Database will be empty. Copy 03_seed_data.dump to the deploy parent directory for auto-import."
        return 0
    fi

    info "Importing seed data (this may take a few minutes)..."

    # Copy dump into container
    docker cp "$dump_file" wind-power-kingbase:/tmp/seed.dump

    # Restore using sys_restore (pg_restore equivalent)
    if docker exec --user kingbase wind-power-kingbase \
        sys_restore -p 54321 -U "$db_user" -d "$db_name" -c --if-exists \
        /tmp/seed.dump 2>&1; then
        info "Seed data imported successfully."
    else
        warn "Some warnings during import (this is usually normal for partition tables)."
        warn "Checking if import succeeded..."

        count=$(docker exec --user kingbase wind-power-kingbase \
            "$ksql" -p 54321 -U "$db_user" -d "$db_name" -t -A \
            -c "SELECT count(*) FROM wind_farms;" 2>/dev/null | tr -d '[:space:]')

        if [ "$count" != "0" ] && [ -n "$count" ]; then
            info "Import verified: $count wind farms found."
        else
            error "Seed import may have failed. Check database manually."
        fi
    fi

    # Clean up
    docker exec wind-power-kingbase rm -f /tmp/seed.dump 2>/dev/null || true
}

create_dirs() {
    info "Creating data directories..."

    # Celery worker data (prediction pipeline)
    ensure_dir datasets predict_inputs models predict_outputs logs_middle
    ensure_dir merged_predict_outputs feature_importance_mid
    ensure_dir datasets_short predict_inputs_short models_short predict_outputs_short
    ensure_dir logs_short feature_importance_short
    ensure_dir datasets_ss saved_models_ss prediction_inputs_ss prediction_results_ss logs_ss

    # Backend persistent data
    ensure_dir backend-data/forecast_models
    ensure_dir backend-data/uploads
    ensure_dir backend-data/forecasts
    ensure_dir backend-data/logs
    ensure_dir backend-data/saved_models
    ensure_dir backend-data/saved_scalers
    ensure_dir backend-data/saved_metrics
    ensure_dir backend-data/data_etext
    ensure_dir backend-data/archives

    # Redis persistent data
    ensure_dir redis-data

    # Celery beat schedule data
    ensure_dir celery-beat-data

    # pgAdmin data
    ensure_dir pgadmin-data
    chmod 777 pgadmin-data 2>/dev/null || chown 5050:5050 pgadmin-data 2>/dev/null || true

    # KingBase data (if using db compose)
    ensure_dir kingbase-data
    chmod 777 kingbase-data 2>/dev/null || true
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
    generate_app_env
    create_dirs

    info "Starting database..."
    docker_compose -f docker-compose.db.yaml up -d

    wait_for_database
    ensure_app_database
    import_seed_data

    info "Starting prediction system..."
    docker_compose -f docker-compose.prod.yaml up -d

    info "=== All services started ==="
    info "Frontend:    http://<server-ip>:8080"
    info "Backend API: http://<server-ip>:5000"
    info "pgAdmin:     http://<server-ip>:5050"
}

do_stop() {
    info "Stopping prediction system..."
    docker_compose -f docker-compose.prod.yaml down >/dev/null 2>&1 || true

    info "Stopping database..."
    docker_compose -f docker-compose.db.yaml down >/dev/null 2>&1 || true

    info "All services stopped."
}

do_status() {
    echo ""
    echo "=== Database ==="
    docker_compose -f docker-compose.db.yaml ps 2>/dev/null || echo "  Not started"
    echo ""
    echo "=== Prediction System ==="
    docker_compose -f docker-compose.prod.yaml ps 2>/dev/null || echo "  Not started"
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
    docker_compose -f docker-compose.db.yaml up -d
    wait_for_database
    ensure_app_database
    info "Database started on port 54321"
}

do_logs() {
    local svc="${1:-}"
    if [ -n "$svc" ]; then
        docker_compose -f docker-compose.prod.yaml logs -f "$svc" 2>/dev/null || \
        docker_compose -f docker-compose.db.yaml logs -f "$svc"
    else
        docker_compose -f docker-compose.prod.yaml logs -f 2>/dev/null &
        docker_compose -f docker-compose.db.yaml logs -f 2>/dev/null &
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
