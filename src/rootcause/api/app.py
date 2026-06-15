import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from rootcause.api.routes import health, incidents
from rootcause.core.config import get_settings
from rootcause.core.logging import configure_logging, get_logger
from rootcause.core.telemetry import init_otel, instrument_app
from rootcause.db import (
    close_neo4j,
    close_postgres,
    close_redis,
    close_qdrant,
    init_neo4j,
    init_postgres,
    init_redis,
    init_qdrant,
)

logger = get_logger(__name__)

_OPTIONAL_DBS = [
    ("Redis", init_redis, close_redis),
    ("Qdrant", init_qdrant, close_qdrant),
    ("Neo4j", init_neo4j, close_neo4j),
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    logger.info("rootcause_starting", env=settings.app_env)

    init_otel(settings.app_env)

    # PostgreSQL is required — raise if unavailable
    await init_postgres()

    # Optional databases — warn and continue if unavailable
    for name, init_fn, _ in _OPTIONAL_DBS:
        try:
            await init_fn()
        except Exception as exc:
            logger.warning(f"{name.lower()}_unavailable", error=str(exc))

    yield

    logger.info("rootcause_shutdown")
    await close_postgres()
    for name, _, close_fn in _OPTIONAL_DBS:
        try:
            await close_fn()
        except Exception:
            pass


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="RootCause",
        description="Autonomous Incident RCA and Response Copilot",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_env != "production" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
        )
        return response

    app.include_router(health.router)
    app.include_router(incidents.router)

    instrument_app(app)

    return app
