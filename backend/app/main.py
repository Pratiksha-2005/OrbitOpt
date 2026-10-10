"""Main FastAPI Application Entrypoint for OrbitOpt."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.endpoints.health import check_health
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import OrbitOptException
from app.db.base import Base
from app.db.seeder import seed_standard_datasets
from app.db.session import async_engine, AsyncSessionLocal
from app.schemas.common import HealthResponse

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown routines."""
    # Create tables automatically for sqlite/dev setups
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Seed standard benchmark datasets
    async with AsyncSessionLocal() as session:
        await seed_standard_datasets(session)

    yield
    # Cleanup / dispose engine connection pool
    await async_engine.dispose()


def create_application() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_TITLE,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handlers
    @app.exception_handler(OrbitOptException)
    async def orbitopt_exception_handler(
        request: Request,
        exc: OrbitOptException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "error_code": exc.error_code,
                "details": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Request payload validation failed.",
                "error_code": "VALIDATION_ERROR",
                "details": jsonable_encoder(exc.errors()),
            },
        )

    # Root health endpoint
    app.add_api_route(
        "/health",
        endpoint=check_health,
        methods=["GET"],
        response_model=HealthResponse,
        tags=["Health"],
        summary="Root Health Check",
    )

    # Mount API v1 router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app


app = create_application()
