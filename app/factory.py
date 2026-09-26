"""Application factory for IaC DriftWatch.

``create_app()`` is invoked exactly once by ``main.py`` at process start to
construct and wire the FastAPI instance::

    from app.factory import create_app

    app = create_app()
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.exception_handlers import register_exception_handlers
from app.lifespan import lifespan
from app.middleware import register_middleware

__all__ = ["create_app"]


def create_app() -> FastAPI:
    """Build, configure, and return the FastAPI application instance."""
    app_settings = settings.app
    feature_flags = settings.features
    docs_enabled = feature_flags.enable_api_docs

    app = FastAPI(
        title=app_settings.name,
        version=app_settings.version,
        debug=app_settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    register_middleware(app)
    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix=app_settings.api_prefix)

    @app.get("/", include_in_schema=False)
    async def api_dashboard() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app
