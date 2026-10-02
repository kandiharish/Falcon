"""FALCON API entry point."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.ai.provider import AIUnavailable
from app.api import (
    admin,
    ai,
    auth,
    correlations,
    evidence,
    extraction,
    graph,
    health,
    investigations,
    overview,
    reports,
    work,
)
from app.core.config import get_settings
from app.security.csrf import CSRFHeaderMiddleware
from app.services.errors import DomainError


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} API",
        description="Forensic Analysis and Linked Crime Observation Network",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(CSRFHeaderMiddleware)

    # Services raise domain errors with human-readable messages; send them as JSON.
    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, error: DomainError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"detail": error.message})

    # The local AI service is optional: say so clearly instead of failing with a 500.
    @app.exception_handler(AIUnavailable)
    async def ai_unavailable_handler(_: Request, error: AIUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(error)})

    # Every route lives under /api, so the frontend can proxy one prefix.
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(investigations.router, prefix="/api")
    app.include_router(evidence.router, prefix="/api")
    app.include_router(extraction.router, prefix="/api")
    app.include_router(correlations.router, prefix="/api")
    app.include_router(graph.router, prefix="/api")
    app.include_router(ai.router, prefix="/api")
    app.include_router(work.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")
    app.include_router(overview.router, prefix="/api")
    return app


app = create_app()
