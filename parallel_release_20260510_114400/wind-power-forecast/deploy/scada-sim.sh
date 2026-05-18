#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

docker_cmd() {
    MSYS_NO_PATHCONV=1 \
    MSYS2_ARG_CONV_EXCL="*" \
    docker "$@"
}

docker_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_IGNORE_ORPHANS=true \
        COMPOSE_CONVERT_WINDOWS_PATHS=1 \
        MSYS_NO_PATHCONV=1 \
        MSYS2_ARG_CONV_EXCL="*" \
        docker compose "$@"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_IGNORE_ORPHANS=true \
        COMPOSE_CONVERT_WINDOWS_PATHS=1 \
        MSYS_NO_PATHCONV=1 \
        MSYS2_ARG_CONV_EXCL="*" \
        docker-compose "$@"
    else
        error "Docker Compose is not available. Install docker compose plugin or docker-compose."
        exit 1
    fi
}

check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        error "Docker is not installed."
        exit 1
    fi
    if ! docker info >/dev/null 2>&1; then
        error "Docker daemon is not running."
        exit 1
    fi
    if ! docker compose version >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
        error "Docker Compose is not available. Install docker compose plugin or docker-compose."
        exit 1
    fi
}

create_network() {
    if ! docker network inspect wind-power-staging-network >/dev/null 2>&1; then
        info "Creating Docker network: wind-power-staging-network"
        docker network create wind-power-staging-network
    fi
}

load_env() {
    if [ -f .env ]; then
        set -a
        source .env
        set +a
    fi
}

wait_for_database() {
    info "Waiting for wind-power-staging-kingbase..."
    for i in $(seq 1 60); do
        if docker_cmd exec wind-power-staging-kingbase \
            /home/kingbase/install/kingbase/bin/sys_isready \
            -h 127.0.0.1 -p 54321 >/dev/null 2>&1; then
            info "Database is ready."
            return 0
        fi
        sleep 2
    done
    error "Database health check timeout."
    exit 1
}

do_install() {
    check_docker
    if [ -f ../04_scada_simulator.tar ]; then
        info "Loading SCADA simulator image..."
        docker load -i ../04_scada_simulator.tar
    else
        warn "04_scada_simulator.tar not found. Skipping image load."
    fi
    create_network
}

do_start() {
    check_docker
    load_env
    create_network
    docker_compose -f docker-compose.scada-sim.yaml up -d
}

do_stop() {
    docker_compose -f docker-compose.scada-sim.yaml down >/dev/null 2>&1 || true
}

do_seed() {
    check_docker
    load_env
    wait_for_database
    if [ ! -f seed-scada-sim.sql ]; then
        error "seed-scada-sim.sql not found."
        exit 1
    fi
    info "Seeding SCADA simulator connection settings..."
    docker_cmd exec -i --user kingbase wind-power-staging-kingbase \
        /home/kingbase/install/kingbase/bin/ksql \
        -p 54321 -U "${DB_USER:-system}" -d "${DB_NAME:-windpower}" \
        < seed-scada-sim.sql
}

do_status() {
    docker_compose -f docker-compose.scada-sim.yaml ps
    docker_cmd exec --user kingbase wind-power-staging-kingbase \
        /home/kingbase/install/kingbase/bin/ksql \
        -p 54321 -U "${DB_USER:-system}" -d "${DB_NAME:-windpower}" \
        -c "select farm_code, server_ip, server_port, ioa_points, status from scada_connections order by farm_code;" \
        2>/dev/null || true
}

case "${1:-}" in
    install) do_install ;;
    start)   do_start ;;
    stop)    do_stop ;;
    seed)    do_seed ;;
    status)  do_status ;;
    logs)    docker_compose -f docker-compose.scada-sim.yaml logs -f ;;
    *)
        echo "Usage: $0 {install|start|stop|seed|status|logs}"
        echo ""
        echo "Typical flow:"
        echo "  bash scada-sim.sh install"
        echo "  bash scada-sim.sh start"
        echo "  bash scada-sim.sh seed"
        exit 1
        ;;
esac
