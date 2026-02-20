#!/usr/bin/env bash
# Wait for all services to be healthy before proceeding.
set -e

MAX_WAIT=120
WAITED=0

echo "Waiting for services to be ready..."

# Wait for API
echo -n "  API (localhost:8000)..."
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
  sleep 2
  WAITED=$((WAITED + 2))
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo " TIMEOUT"
    exit 1
  fi
  echo -n "."
done
echo " OK"

# Wait for Qdrant
echo -n "  Qdrant (localhost:6333)..."
WAITED=0
until curl -sf http://localhost:6333/healthz > /dev/null 2>&1; do
  sleep 2
  WAITED=$((WAITED + 2))
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo " TIMEOUT"
    exit 1
  fi
  echo -n "."
done
echo " OK"

# Wait for Redis
echo -n "  Redis (localhost:6379)..."
WAITED=0
until redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; do
  sleep 2
  WAITED=$((WAITED + 2))
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo " TIMEOUT (non-critical)"
    break
  fi
  echo -n "."
done
echo " OK"

echo "All services ready!"
