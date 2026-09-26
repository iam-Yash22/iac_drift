#!/usr/bin/env sh
set -eu

export PORT="${PORT:-8000}"
export APP_MODULE="${APP_MODULE:-main:app}"
export APP_SERVER="${APP_SERVER:-gunicorn}"
export GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
export GUNICORN_WORKER_CLASS="${GUNICORN_WORKER_CLASS:-uvicorn.workers.UvicornWorker}"

if [ -n "${DATABASE_URL:-}" ] || [ -n "${POSTGRES_HOST:-}" ] || [ -n "${DB_HOST:-}" ]; then
  echo "Running database migrations..."
  alembic upgrade head
else
  echo "No database connection env vars detected; skipping alembic upgrade."
fi

if [ "$APP_SERVER" = "uvicorn" ]; then
  exec uvicorn "$APP_MODULE" \
    --host 0.0.0.0 \
    --port "$PORT" \
    ${UVICORN_EXTRA_ARGS:-}
elif [ "$APP_SERVER" = "gunicorn" ]; then
  exec gunicorn "$APP_MODULE" \
    --bind "0.0.0.0:$PORT" \
    --workers "$GUNICORN_WORKERS" \
    --worker-class "$GUNICORN_WORKER_CLASS" \
    ${GUNICORN_EXTRA_ARGS:-}
else
  echo "Unsupported APP_SERVER value: $APP_SERVER" >&2
  exit 1
fi
