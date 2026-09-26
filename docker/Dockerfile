# Multi-stage build: builder creates a venv and installs pinned deps from requirements.txt
FROM python:3.12-slim AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements first to leverage cache
COPY requirements.txt ./

# Create and use a virtualenv inside the image
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy app sources (will be copied to final image as well)
COPY . /app

### Runtime image
FROM python:3.12-slim

# Create a non-root user to run the app
RUN groupadd --system appuser \
    && useradd --system --gid appuser --create-home --home-dir /home/appuser appuser

WORKDIR /app

# Copy the venv from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Copy application files and set safe ownership
COPY --chown=appuser:appuser . /app

# Ensure entrypoint and healthcheck are executable if present
RUN chmod +x /app/entrypoint.sh /app/healthcheck.sh || true

USER appuser

EXPOSE 8000

# Runtime entrypoint (expects `/app/entrypoint.sh` to exist and be executable)
ENTRYPOINT ["/app/entrypoint.sh"]
