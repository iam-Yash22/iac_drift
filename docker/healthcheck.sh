#!/usr/bin/env sh
set -eu

HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:${PORT:-8000}/api/v1/health}"

curl --fail --silent --show-error --max-time 5 "$HEALTH_URL" > /dev/null
