import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import engine, get_db
from app.core.redis import get_redis
from app.core.security import get_current_user
from app.models.agent import Agent
from app.models.conversation import Conversation, Message
from app.models.knowledge import KnowledgeBase, KnowledgeDocument
from app.models.mcp import McpConnector
from app.models.user import User
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/system", tags=["System"])
logger = logging.getLogger(__name__)

SETTINGS_REDIS_KEY_PREFIX = "bridgeai:settings:"


class SystemSettings(BaseModel):
    """System settings that can be saved per-tenant."""
    default_model: Optional[str] = None
    default_temperature: Optional[float] = None
    stream_enabled: Optional[bool] = None
    content_filter_enabled: Optional[bool] = None
    platform_name: Optional[str] = None
    language: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    audit_log_enabled: Optional[bool] = None


@router.get("/settings", response_model=ApiResponse[Dict[str, Any]])
async def get_settings(
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """Get system settings for the current tenant."""
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else "default"
    try:
        redis = await get_redis()
        raw = await redis.get(f"{SETTINGS_REDIS_KEY_PREFIX}{tenant_id}")
        if raw:
            data = json.loads(raw)
        else:
            data = SystemSettings().model_dump()
        return ApiResponse.success(data=data)
    except Exception as e:
        logger.warning("Failed to load settings from Redis: %s", e)
        return ApiResponse.success(data=SystemSettings().model_dump())


@router.put("/settings", response_model=ApiResponse[Dict[str, Any]])
async def update_settings(
    body: SystemSettings = Body(...),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """Save system settings for the current tenant to Redis."""
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else "default"
    try:
        redis = await get_redis()
        # Merge with existing settings
        existing_raw = await redis.get(f"{SETTINGS_REDIS_KEY_PREFIX}{tenant_id}")
        existing: Dict[str, Any] = json.loads(existing_raw) if existing_raw else {}
        # Only update non-None fields
        update_data = body.model_dump(exclude_none=True)
        existing.update(update_data)
        await redis.set(
            f"{SETTINGS_REDIS_KEY_PREFIX}{tenant_id}",
            json.dumps(existing),
        )
        return ApiResponse.success(data=existing, message="设置已保存")
    except Exception as e:
        logger.error("Failed to save settings to Redis: %s", e)
        return ApiResponse.error(code=500, message=f"保存设置失败: {str(e)}")


@router.get("/health", response_model=ApiResponse[Dict[str, Any]])
async def health_check() -> ApiResponse:
    """Check system health: database and Redis connectivity."""
    health: Dict[str, Any] = {
        "status": "healthy",
        "database": "unknown",
        "redis": "unknown",
        "minio": "unknown",
    }

    # Check database
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text

            await conn.execute(text("SELECT 1"))
        health["database"] = "connected"
    except Exception as e:
        health["database"] = f"error: {str(e)}"
        health["status"] = "degraded"
        logger.warning("Database health check failed: %s", e)

    # Check Redis
    try:
        redis = await get_redis()
        await redis.ping()
        health["redis"] = "connected"
    except Exception as e:
        health["redis"] = f"error: {str(e)}"
        health["status"] = "degraded"
        logger.warning("Redis health check failed: %s", e)

    # Check MinIO
    try:
        from app.services.storage_service import storage_service
        if storage_service.is_available():
            health["minio"] = "connected"
        else:
            health["minio"] = "error: not reachable"
            health["status"] = "degraded"
    except Exception as e:
        health["minio"] = f"error: {str(e)}"
        health["status"] = "degraded"
        logger.warning("MinIO health check failed: %s", e)

    return ApiResponse.success(data=health)


@router.get("/files/{bucket}/{object_key:path}")
async def download_file(
    bucket: str,
    object_key: str,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Download a file from MinIO via presigned URL redirect.

    bucket: one of documents, attachments, avatars, exports
    object_key: the full object key path
    """
    from fastapi.responses import RedirectResponse

    valid_buckets = {"documents", "attachments", "avatars", "exports"}
    if bucket not in valid_buckets:
        return ApiResponse.error(code=400, message=f"无效的 bucket: {bucket}")

    try:
        from app.services.storage_service import storage_service
        url = storage_service.get_presigned_url(bucket, object_key, expires_hours=1)
        return RedirectResponse(url=url)
    except Exception as e:
        logger.error("Failed to generate presigned URL for %s/%s: %s", bucket, object_key, e)
        return ApiResponse.error(code=500, message=f"获取下载链接失败: {str(e)}")


@router.get("/models", response_model=ApiResponse[List[Dict[str, Any]]])
async def list_models() -> ApiResponse:
    """List available LLM models."""
    models: List[Dict[str, Any]] = [
        {
            "id": "claude-sonnet-4-20250514",
            "name": "Claude Sonnet 4",
            "provider": "anthropic",
            "available": bool(settings.ANTHROPIC_API_KEY),
        },
        {
            "id": "claude-opus-4-20250514",
            "name": "Claude Opus 4",
            "provider": "anthropic",
            "available": bool(settings.ANTHROPIC_API_KEY),
        },
        {
            "id": "deepseek-chat",
            "name": "DeepSeek Chat",
            "provider": "deepseek",
            "available": bool(settings.DEEPSEEK_API_KEY),
        },
        {
            "id": "deepseek-reasoner",
            "name": "DeepSeek Reasoner",
            "provider": "deepseek",
            "available": bool(settings.DEEPSEEK_API_KEY),
        },
        {
            "id": "qwen-plus",
            "name": "Qwen Plus",
            "provider": "qwen",
            "available": bool(settings.QWEN_API_KEY),
        },
        {
            "id": "qwen-max",
            "name": "Qwen Max",
            "provider": "qwen",
            "available": bool(settings.QWEN_API_KEY),
        },
    ]
    return ApiResponse.success(data=models)


@router.get("/stats", response_model=ApiResponse[Dict[str, Any]])
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """Return dashboard statistics queried from the database."""
    tenant_id = current_user.tenant_id

    # --- Totals ---
    conversations_count = (
        await db.scalar(
            select(func.count()).select_from(Conversation).where(Conversation.tenant_id == tenant_id)
        )
    ) or 0

    messages_count = (
        await db.scalar(
            select(func.count()).select_from(Message).where(Message.tenant_id == tenant_id)
        )
    ) or 0

    agents_count = (
        await db.scalar(
            select(func.count()).select_from(Agent).where(Agent.tenant_id == tenant_id)
        )
    ) or 0

    mcp_count = (
        await db.scalar(
            select(func.count()).select_from(McpConnector).where(McpConnector.tenant_id == tenant_id)
        )
    ) or 0

    kb_count = (
        await db.scalar(
            select(func.count()).select_from(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant_id)
        )
    ) or 0

    doc_count = (
        await db.scalar(
            select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.tenant_id == tenant_id)
        )
    ) or 0

    # --- Daily usage (last 7 days) ---
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    daily_rows = (
        await db.execute(
            text(
                """
                SELECT
                    date_trunc('day', created_at)::date AS day,
                    COUNT(*)::int AS messages,
                    COALESCE(SUM(token_input + token_output), 0)::int AS tokens
                FROM messages
                WHERE tenant_id = :tid AND created_at >= :since
                GROUP BY day
                ORDER BY day
                """
            ),
            {"tid": str(tenant_id), "since": seven_days_ago},
        )
    ).fetchall()

    daily_usage: List[Dict[str, Any]] = [
        {"date": str(row.day), "messages": row.messages, "tokens": row.tokens}
        for row in daily_rows
    ]

    # --- Intent distribution ---
    intent_rows = (
        await db.execute(
            text(
                """
                SELECT intent, COUNT(*)::int AS count
                FROM messages
                WHERE tenant_id = :tid AND intent IS NOT NULL AND intent != ''
                GROUP BY intent
                ORDER BY count DESC
                """
            ),
            {"tid": str(tenant_id)},
        )
    ).fetchall()

    intent_distribution: List[Dict[str, Any]] = [
        {"intent": row.intent, "count": row.count} for row in intent_rows
    ]

    # --- Emotion distribution ---
    emotion_rows = (
        await db.execute(
            text(
                """
                SELECT emotion, COUNT(*)::int AS count
                FROM messages
                WHERE tenant_id = :tid AND emotion IS NOT NULL AND emotion != ''
                GROUP BY emotion
                ORDER BY count DESC
                """
            ),
            {"tid": str(tenant_id)},
        )
    ).fetchall()

    emotion_distribution: List[Dict[str, Any]] = [
        {"emotion": row.emotion, "count": row.count} for row in emotion_rows
    ]

    # --- Model usage ---
    model_rows = (
        await db.execute(
            text(
                """
                SELECT model_used AS model, COUNT(*)::int AS count
                FROM messages
                WHERE tenant_id = :tid AND model_used IS NOT NULL AND model_used != ''
                GROUP BY model_used
                ORDER BY count DESC
                """
            ),
            {"tid": str(tenant_id)},
        )
    ).fetchall()

    model_usage: List[Dict[str, Any]] = [
        {"model": row.model, "count": row.count} for row in model_rows
    ]

    return ApiResponse.success(
        data={
            "total_conversations": conversations_count,
            "total_messages": messages_count,
            "total_agents": agents_count,
            "total_mcp_connectors": mcp_count,
            "total_knowledge_bases": kb_count,
            "total_documents": doc_count,
            "daily_usage": daily_usage,
            "intent_distribution": intent_distribution,
            "emotion_distribution": emotion_distribution,
            "model_usage": model_usage,
        }
    )
