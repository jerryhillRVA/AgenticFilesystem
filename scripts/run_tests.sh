#!/usr/bin/env bash
# Start Docker Compose, wait for services, run tests, then optionally tear down.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== Starting Docker Compose ==="
docker compose up -d --build

echo ""
echo "=== Waiting for Services ==="
bash scripts/wait_for_services.sh

echo ""
echo "=== Running Tests ==="
python -m pytest tests/ -v --tb=short

echo ""
echo "=== Tests Complete ==="
echo "Services are still running. Use 'docker compose down' to stop them."
