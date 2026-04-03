"""Notification API — list, mark read, mark all read."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.core.security import get_current_user
from app.models.notification import Notification
from app.models.user import User
from app.schemas.common import ApiResponse, PageResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])
logger = logging.getLogger(__name__)


def _notification_to_dict(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "title": n.title,
        "content": n.content or "",
        "type": n.type,
        "isRead": n.is_read,
        "createdAt": n.created_at.isoformat() if n.created_at else "",
    }


@router.get("", response_model=ApiResponse[PageResponse])
async def list_notifications(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List notifications for the current user, newest first."""
    user_id = current_user.id
    base_query = select(Notification).where(Notification.user_id == user_id)

    count_q = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        base_query
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = [_notification_to_dict(n) for n in result.scalars().all()]
    pages = (total + size - 1) // size

    # Also include unread count for badge
    unread_q = select(func.count()).select_from(
        select(Notification.id)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .subquery()
    )
    unread_count = (await db.execute(unread_q)).scalar() or 0

    return ApiResponse.success(
        data={
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "pages": pages,
            "unreadCount": unread_count,
        }
    )


@router.get("/unread-count", response_model=ApiResponse)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Get unread notification count for badge display."""
    user_id = current_user.id
    unread_q = select(func.count()).select_from(
        select(Notification.id)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .subquery()
    )
    count = (await db.execute(unread_q)).scalar() or 0
    return ApiResponse.success(data={"count": count})


@router.put("/{notification_id}/read", response_model=ApiResponse)
async def mark_as_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Mark a single notification as read."""
    import uuid as _uuid
    try:
        nid = _uuid.UUID(notification_id)
    except ValueError:
        raise NotFoundException(message="通知不存在")

    result = await db.execute(
        select(Notification).where(
            Notification.id == nid,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise NotFoundException(message="通知不存在")

    notification.is_read = True
    await db.flush()
    return ApiResponse.success(message="已标记为已读")


@router.put("/read-all", response_model=ApiResponse)
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Mark all notifications as read for the current user."""
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await db.flush()
    return ApiResponse.success(message="全部已读")
