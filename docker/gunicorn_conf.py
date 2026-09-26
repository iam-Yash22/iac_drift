import multiprocessing
import os

workers = max(2, multiprocessing.cpu_count() * 2 + 1)
worker_class = "uvicorn.workers.UvicornWorker"
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
keepalive = 120
timeout = 30

# Recommended defaults for containerized deployments.
# Keep the configuration independent from app code so Gunicorn can load it directly.
