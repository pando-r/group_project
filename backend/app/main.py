from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent.runner import agent_runtime
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import install_exception_handlers, trace_id_ctx
from app.core.logging import configure_logging, get_logger
from app.db.seed import seed_database
from app.db.session import SessionLocal, close_database, init_database
from app.rules.constants import ACTIVE_RULE_VERSION

configure_logging(debug=settings.log_debug)
logger = get_logger("medrisk.app")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_database()
    if settings.auto_seed:
        async with SessionLocal() as session:
            try:
                seeded = await seed_database(session)
            except Exception:
                await session.rollback()
                raise
        if seeded:
            logger.info("demo_seed_created")
    await agent_runtime.start()
    logger.info(
        "application_started",
        env=settings.app_env,
        database="sqlite" if settings.is_sqlite else "postgresql",
        rule_version=ACTIVE_RULE_VERSION,
        llm_mock=settings.llm_mock,
    )
    yield
    await agent_runtime.stop()
    await close_database()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="专科疾病智能风险分级系统 · 演示原型。概率未经校准，不替代医生决策。",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    trace_id = request.headers.get("X-Trace-Id") or uuid4().hex
    token = trace_id_ctx.set(trace_id)
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed",
            method=request.method,
            path=request.url.path,
        )
        raise
    finally:
        trace_id_ctx.reset(token)

    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    response.headers["X-Trace-Id"] = trace_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        latency_ms=elapsed_ms,
    )
    structlog.contextvars.clear_contextvars()
    return response


install_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["ops"])
async def health() -> JSONResponse:
    from sqlalchemy import text

    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        logger.exception("health_database_failed")
        database = "error"
    status_code = 200 if database == "ok" else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if status_code == 200 else "degraded",
            "service": settings.app_name,
            "environment": settings.app_env,
            "database": database,
            "ruleVersion": ACTIVE_RULE_VERSION,
        },
    )


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "docs": "/docs",
        "health": "/health",
    }
