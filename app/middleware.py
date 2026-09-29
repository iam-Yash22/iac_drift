"""HTTP middleware registration.

Registers cross-cutting middleware onto the FastAPI instance. Each inbound
request passes through this stack (outermost first) before route dispatch::

    Request-ID -> Timing -> GZip -> CORS -> route handler
"""

from __future__ import annotations

import os
import time
import uuid
from typing import TYPE_CHECKING

from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.core.config import settings

if TYPE_CHECKING:
    from fastapi import FastAPI
    from starlette.requests import Request
    from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
PROCESS_TIME_HEADER = "X-Process-Time"
GZIP_MINIMUM_SIZE_BYTES = 1000


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assign a stable request identifier for tracing across log lines."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Measure end-to-end request processing time."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers[PROCESS_TIME_HEADER] = f"{elapsed_ms:.2f}ms"
        return response


def _resolve_cors_origins() -> list[str]:
    """Resolve allowed CORS origins directly from the environment.

    Bypasses settings.cors.allow_origins, which does not reliably pick up
    CORS_ORIGINS / CORS__ALLOW_ORIGINS due to nested-model resolution.
    Reads the raw env var as the source of truth when present; falls back
    to whatever Settings resolved otherwise.
    """
    env_value = os.getenv("CORS_ORIGINS") or os.getenv("CORS__ALLOW_ORIGINS")
    if env_value:
        origins = [origin.strip() for origin in env_value.split(",") if origin.strip()]
    else:
        origins = list(settings.cors.allow_origins)
    return list(dict.fromkeys(origins))


def register_middleware(app: FastAPI) -> None:
    """Attach cross-cutting middleware to the application.

    Middleware is registered inner-first so the runtime execution order is
    request-ID, timing, compression, CORS, then the route handler.
    """
    cors = settings.cors
    allowed_origins = _resolve_cors_origins()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=cors.allow_credentials,
        allow_methods=cors.allow_methods,
        allow_headers=cors.allow_headers,
    )
    app.add_middleware(GZipMiddleware, minimum_size=GZIP_MINIMUM_SIZE_BYTES)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)
