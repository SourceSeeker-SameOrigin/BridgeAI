import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.core.database import engine
from app.core.tenant_filter import setup_tenant_filter
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
    http_exception_handler,
)
from app.core.redis import close_redis, get_redis
from app.middleware.content_filter import ContentFilterMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.tenant import TenantMiddleware
from app.models.base import Base

# Import all models so SQLAlchemy registers them
from app.models import user, agent, conversation, mcp, knowledge, plugin, audit, workflow, payment, notification  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialize DB tables and Redis on startup, cleanup on shutdown."""
    logger.info("Starting BridgeAI backend v%s", settings.APP_VERSION)

    # Database schema is managed by Alembic migrations.
    # Run: alembic upgrade head
    logger.info("Database schema managed by Alembic migrations")

    # Register multi-tenant SQL safety-net filter
    setup_tenant_filter(engine)

    # Warm up Redis connection
    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning("Redis connection skipped (not available): %s", e)

    yield

    # Cleanup
    await close_redis()
    await engine.dispose()
    logger.info("BridgeAI backend shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="BridgeAI - Intelligent Agent Platform API",
    lifespan=lifespan,
    docs_url=None,  # Disable default, use custom below
    redoc_url="/redoc",
)


# Custom Swagger UI with offline CDN fallback
from fastapi.openapi.docs import get_swagger_ui_html

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title=f"{settings.APP_NAME} - API Docs",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static files (Swagger UI offline) ---
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# --- Security Headers Middleware ---
app.add_middleware(SecurityHeadersMiddleware)

# --- Rate Limiting Middleware ---
app.add_middleware(RateLimitMiddleware)

# --- Sensitive Content Filter Middleware (chat endpoints only) ---
app.add_middleware(ContentFilterMiddleware)

# --- Tenant Middleware ---
app.add_middleware(TenantMiddleware)

# --- Exception Handlers ---
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# --- Routers ---
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.agents import router as agents_router
from app.api.v1.mcp import router as mcp_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.system import router as system_router
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.plugins import router as plugins_router
from app.api.v1.channels import router as channels_router
from app.api.v1.audit import router as audit_router
from app.api.v1.billing import router as billing_router
from app.api.v1.workflows import router as workflows_router
from app.api.v1.payment import router as payment_router
from app.api.v1.users import router as users_router
from app.api.v1.search import router as search_router
from app.api.v1.notifications import router as notifications_router

API_V1_PREFIX = "/api/v1"

app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(chat_router, prefix=API_V1_PREFIX)
app.include_router(agents_router, prefix=API_V1_PREFIX)
app.include_router(mcp_router, prefix=API_V1_PREFIX)
app.include_router(knowledge_router, prefix=API_V1_PREFIX)
app.include_router(system_router, prefix=API_V1_PREFIX)
app.include_router(api_keys_router, prefix=API_V1_PREFIX)
app.include_router(plugins_router, prefix=API_V1_PREFIX)
app.include_router(channels_router, prefix=API_V1_PREFIX)
app.include_router(audit_router, prefix=API_V1_PREFIX)
app.include_router(billing_router, prefix=API_V1_PREFIX)
app.include_router(workflows_router, prefix=API_V1_PREFIX)
app.include_router(payment_router, prefix=API_V1_PREFIX)
app.include_router(users_router, prefix=API_V1_PREFIX)
app.include_router(search_router, prefix=API_V1_PREFIX)
app.include_router(notifications_router, prefix=API_V1_PREFIX)


# --- Prometheus Metrics ---
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/")
async def root() -> dict:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
