"""FALCON API entry point."""

from fastapi import FastAPI

from app.api import admin, auth, health
from app.core.config import get_settings
from app.security.csrf import CSRFHeaderMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} API",
        description="Forensic Analysis and Linked Crime Observation Network",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(CSRFHeaderMiddleware)
    # Every route lives under /api, so the frontend can proxy one prefix.
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    return app


app = create_app()
