#!/usr/bin/env bash
#
# dockerStart.sh — Manage the Agentic Filesystem Docker Compose stack
#
# Usage:
#   ./dockerStart.sh --start       Start all services (build if needed)
#   ./dockerStart.sh --rebuild     Force rebuild images and restart
#   ./dockerStart.sh --stop        Stop all services
#   ./dockerStart.sh --logs        Tail logs from all services
#   ./dockerStart.sh --logs api    Tail logs from a specific service
#   ./dockerStart.sh --clean       Wipe all data (volumes) and restart fresh
#   ./dockerStart.sh --status      Show service status
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║       Agentic Filesystem              ║"
    echo "║       Docker Compose Manager          ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

wait_for_healthy() {
    local max_wait=90
    local waited=0

    echo -e "${YELLOW}Waiting for services to be healthy...${NC}"

    # Wait for API
    printf "  API (port 8000)..."
    until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
        sleep 2
        waited=$((waited + 2))
        if [ "$waited" -ge "$max_wait" ]; then
            echo -e " ${RED}TIMEOUT${NC}"
            echo -e "${RED}API failed to start. Check logs: ./dockerStart.sh --logs api${NC}"
            return 1
        fi
        printf "."
    done
    echo -e " ${GREEN}OK${NC}"

    # Wait for Qdrant
    printf "  Qdrant (port 6333)..."
    waited=0
    until curl -sf http://localhost:6333/healthz > /dev/null 2>&1; do
        sleep 2
        waited=$((waited + 2))
        if [ "$waited" -ge "$max_wait" ]; then
            echo -e " ${RED}TIMEOUT${NC}"
            return 1
        fi
        printf "."
    done
    echo -e " ${GREEN}OK${NC}"

    # Wait for Tika
    printf "  Tika (port 9998)..."
    waited=0
    until curl -sf http://localhost:9998/version > /dev/null 2>&1; do
        sleep 2
        waited=$((waited + 2))
        if [ "$waited" -ge "$max_wait" ]; then
            echo -e " ${YELLOW}TIMEOUT (non-critical)${NC}"
            break
        fi
        printf "."
    done
    echo -e " ${GREEN}OK${NC}"

    echo ""
    echo -e "${GREEN}All services ready!${NC}"
    echo -e "  API Docs:  ${CYAN}http://localhost:8000/docs${NC}"
    echo -e "  Health:    ${CYAN}http://localhost:8000/health${NC}"
    echo -e "  Qdrant UI: ${CYAN}http://localhost:6333/dashboard${NC}"
    echo ""
}

do_start() {
    print_banner
    echo -e "${GREEN}Starting services...${NC}"
    docker compose up -d --build
    echo ""
    wait_for_healthy
    docker compose ps
}

do_rebuild() {
    print_banner
    echo -e "${YELLOW}Rebuilding images and restarting...${NC}"
    docker compose down
    docker compose build --no-cache
    docker compose up -d
    echo ""
    wait_for_healthy
    docker compose ps
}

do_clean() {
    print_banner
    echo -e "${RED}Wiping all data and restarting fresh...${NC}"
    echo -e "${YELLOW}This will delete: uploaded files, Qdrant vectors, Redis state${NC}"
    docker compose down -v
    echo -e "${GREEN}Volumes removed.${NC}"
    echo ""
    echo -e "${GREEN}Starting fresh services...${NC}"
    docker compose up -d --build
    echo ""
    wait_for_healthy
    docker compose ps
}

do_stop() {
    print_banner
    echo -e "${RED}Stopping services...${NC}"
    docker compose down
    echo -e "${GREEN}All services stopped.${NC}"
    echo ""
    echo -e "  To also remove volumes (${RED}deletes all data${NC}): ./dockerStart.sh --clean"
}

do_logs() {
    local service="$1"
    if [ -n "$service" ]; then
        echo -e "${CYAN}Tailing logs for: ${service}${NC}"
        docker compose logs -f "$service"
    else
        echo -e "${CYAN}Tailing logs for all services (Ctrl+C to stop)${NC}"
        docker compose logs -f
    fi
}

do_status() {
    print_banner
    docker compose ps
    echo ""

    # Quick health checks
    echo -e "${CYAN}Health Checks:${NC}"
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "  API:    ${GREEN}healthy${NC}"
    else
        echo -e "  API:    ${RED}unreachable${NC}"
    fi

    if curl -sf http://localhost:6333/healthz > /dev/null 2>&1; then
        echo -e "  Qdrant: ${GREEN}healthy${NC}"
    else
        echo -e "  Qdrant: ${RED}unreachable${NC}"
    fi

    if redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
        echo -e "  Redis:  ${GREEN}healthy${NC}"
    else
        echo -e "  Redis:  ${YELLOW}unreachable (or redis-cli not installed locally)${NC}"
    fi
}

# Parse arguments
case "${1}" in
    --start)
        do_start
        ;;
    --rebuild)
        do_rebuild
        ;;
    --clean)
        do_clean
        ;;
    --stop)
        do_stop
        ;;
    --logs)
        do_logs "$2"
        ;;
    --status)
        do_status
        ;;
    *)
        echo "Usage: $0 {--start|--rebuild|--clean|--stop|--logs [service]|--status}"
        echo ""
        echo "  --start       Start all services (build if images missing)"
        echo "  --rebuild     Force rebuild all images and restart"
        echo "  --clean       Wipe all data (volumes) and restart fresh"
        echo "  --stop        Stop all services"
        echo "  --logs        Tail logs from all services"
        echo "  --logs api    Tail logs from a specific service (api|worker|qdrant|redis|tika)"
        echo "  --status      Show service status and health checks"
        exit 1
        ;;
esac
