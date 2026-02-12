#!/usr/bin/env bash
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────
ENV_NAME="python310"
HOST="0.0.0.0"
PORT=5000
WORKERS=6
THREADS=12
TIMEOUT=120
MAX_REQUESTS=500
MAX_REQUESTS_JITTER=100
GRACEFUL_TIMEOUT=120
LOG_DIR="./logs"

# ── Setup ────────────────────────────────────────────────────────────
mkdir -p "${LOG_DIR}"
source activate "${ENV_NAME}"

# ── Build cache if it doesn't exist yet ──────────────────────────────
if [ ! -d "cache" ] || [ -z "$(ls -A cache 2>/dev/null)" ]; then
    echo "Cache not found — running build.py first..."
    python ./build.py
fi

# ── Launch ───────────────────────────────────────────────────────────
echo "Starting Phydon Growth Rate API on ${HOST}:${PORT} ..."

gunicorn \
    -w "${WORKERS}" \
    --threads="${THREADS}" \
    --worker-class=gthread \
    -b "${HOST}:${PORT}" \
    --timeout "${TIMEOUT}" \
    --max-requests "${MAX_REQUESTS}" \
    --max-requests-jitter "${MAX_REQUESTS_JITTER}" \
    --graceful-timeout "${GRACEFUL_TIMEOUT}" \
    "growth_rate:create_app()" \
    --access-logfile "${LOG_DIR}/access.log" \
    --error-logfile "${LOG_DIR}/error.log"