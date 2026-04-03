"""Notification service — create notifications for system events."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncSession,
    *,
    tenant_id: str | uuid.UUID,
    user_id: str | uuid.UUID,
    title: str,
    content: str = "",
    notification_type: str = "info",
) -> Notification:
    """Create and persist a notification record.

    Args:
        db: Async database session.
        tenant_id: Tenant UUID.
        user_id: Target user UUID.
        title: Short notification title.
        content: Detailed content text.
        notification_type: One of info, success, warning, error.
    """
    n = Notification(
        tenant_id=uuid.UUID(str(tenant_id)),
        user_id=uuid.UUID(str(user_id)),
        title=title,
        content=content,
        type=notification_type,
    )
    db.add(n)
    await db.flush()
    logger.info("Notification created: [%s] %s for user %s", notification_type, title, user_id)
    return n


async def notify_document_indexed(
    db: AsyncSession,
    *,
    tenant_id: str | uuid.UUID,
    user_id: str | uuid.UUID,
    filename: str,
) -> Notification:
    """Notify user that document indexing completed successfully."""
    return await create_notification(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        title=f"文档 {filename} 索引完成",
        content=f"文档 [{filename}] 已完成索引，可在对话中使用。",
        notification_type="success",
    )


async def notify_document_failed(
    db: AsyncSession,
    *,
    tenant_id: str | uuid.UUID,
    user_id: str | uuid.UUID,
    filename: str,
    error: str = "",
) -> Notification:
    """Notify user that document indexing failed."""
    content = f"文档 [{filename}] 索引失败。"
    if error:
        content += f" 错误: {error}"
    return await create_notification(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        title=f"文档 {filename} 索引失败",
        content=content,
        notification_type="error",
    )


async def notify_quota_warning(
    db: AsyncSession,
    *,
    tenant_id: str | uuid.UUID,
    user_id: str | uuid.UUID,
    usage_percent: int = 80,
) -> Notification:
    """Notify user that usage quota is approaching the limit."""
    return await create_notification(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        title=f"本月用量已达 {usage_percent}%",
        content=f"您的本月用量已达到 {usage_percent}%，请注意控制用量或考虑升级套餐。",
        notification_type="warning",
    )


async def notify_plan_upgraded(
    db: AsyncSession,
    *,
    tenant_id: str | uuid.UUID,
    user_id: str | uuid.UUID,
    plan_name: str,
) -> Notification:
    """Notify user that plan has been upgraded."""
    return await create_notification(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        title=f"套餐已升级为 {plan_name}",
        content=f"您的套餐已成功升级为 [{plan_name}]，新套餐已立即生效。",
        notification_type="success",
    )
