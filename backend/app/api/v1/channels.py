"""Channel webhook API — WeChat Work & DingTalk bot callback endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.manager import channel_manager
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["Channels"])


# ======================================================================
# Channel Status (authenticated)
# ======================================================================


@router.get("/status")
async def channel_status(
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """List all channels and their configuration status."""
    channels = channel_manager.list_channels()
    return JSONResponse(
        content={"code": 200, "message": "success", "data": channels},
    )


# ======================================================================
# WeChat Work Callback
# ======================================================================


@router.get("/wechat-work/callback")
async def wechat_work_verify(request: Request) -> PlainTextResponse:
    """Handle WeChat Work URL verification (GET).

    WeChat Work sends a GET request to verify the callback URL.
    We must decrypt echostr and return it as plain text.
    """
    wechat = channel_manager.get_channel("wechat_work")
    if wechat is None or not wechat.is_configured():
        return PlainTextResponse("channel not configured", status_code=503)

    from app.channels.wechat_work import WeChatWorkChannel
    wechat_ch: WeChatWorkChannel = wechat  # type: ignore[assignment]

    result = wechat_ch.handle_url_verification(request)
    if result:
        return PlainTextResponse(result)
    return PlainTextResponse("verification failed", status_code=403)


@router.post("/wechat-work/callback")
async def wechat_work_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Handle WeChat Work message callback (POST).

    This endpoint does NOT require JWT auth — it is called by
    WeChat Work servers with signature verification instead.
    """
    wechat = channel_manager.get_channel("wechat_work")
    if wechat is None or not wechat.is_configured():
        return JSONResponse(
            status_code=200,
            content={"code": 503, "message": "WeChat Work channel not configured", "data": None},
        )

    # Read raw body for signature verification
    body = await request.body()

    # Verify signature
    if not wechat.verify_signature(request, body):
        return JSONResponse(
            status_code=200,
            content={"code": 403, "message": "signature verification failed", "data": None},
        )

    # Parse and handle message
    from app.channels.wechat_work import WeChatWorkChannel
    wechat_ch: WeChatWorkChannel = wechat  # type: ignore[assignment]

    parsed = await wechat_ch.handle_message({"encrypted_body": body.decode("utf-8")})

    channel_user_id = parsed.get("channel_user_id", "")
    content = parsed.get("content", "")
    msg_type = parsed.get("message_type", "")

    if not channel_user_id or not content or msg_type != "text":
        # Non-text or empty messages: acknowledge but don't process
        return JSONResponse(content={"code": 200, "message": "ok", "data": None})

    # Route to chat_service and reply
    reply = await channel_manager.route_message_to_chat(
        channel_name="wechat_work",
        channel_user_id=channel_user_id,
        content=content,
        db=db,
    )

    # Send reply back to user (async, best-effort)
    await channel_manager.send_reply(
        channel_name="wechat_work",
        channel_user_id=channel_user_id,
        content=reply,
    )

    return JSONResponse(content={"code": 200, "message": "ok", "data": None})


# ======================================================================
# Feishu Callback
# ======================================================================


@router.post("/feishu/callback")
async def feishu_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Handle Feishu event callback (POST).

    Handles both URL verification (challenge-response) and
    incoming message events from Feishu bot.
    """
    feishu = channel_manager.get_channel("feishu")
    if feishu is None or not feishu.is_configured():
        return JSONResponse(
            status_code=200,
            content={"code": 503, "message": "Feishu channel not configured", "data": None},
        )

    body = await request.body()

    # Parse JSON payload
    try:
        import json as _json
        payload = _json.loads(body)
    except (ValueError, TypeError):
        return JSONResponse(
            status_code=200,
            content={"code": 400, "message": "invalid payload", "data": None},
        )

    # URL verification (challenge-response)
    from app.channels.feishu_bot import FeishuChannel
    feishu_ch: FeishuChannel = feishu  # type: ignore[assignment]

    verification = feishu_ch.handle_url_verification(payload)
    if verification is not None:
        return JSONResponse(content=verification)

    # Verify signature for event callbacks
    if not feishu.verify_signature(request, body):
        return JSONResponse(
            status_code=200,
            content={"code": 403, "message": "signature verification failed", "data": None},
        )

    # Parse and handle message
    parsed = await feishu_ch.handle_message(payload)

    channel_user_id = parsed.get("channel_user_id", "")
    content = parsed.get("content", "")
    msg_type = parsed.get("message_type", "")

    if not channel_user_id or not content or msg_type != "text":
        return JSONResponse(content={"code": 200, "message": "ok", "data": None})

    # Route to chat_service and reply
    reply = await channel_manager.route_message_to_chat(
        channel_name="feishu",
        channel_user_id=channel_user_id,
        content=content,
        db=db,
    )

    # Send reply back to user
    await channel_manager.send_reply(
        channel_name="feishu",
        channel_user_id=channel_user_id,
        content=reply,
    )

    return JSONResponse(content={"code": 200, "message": "ok", "data": None})


@router.get("/feishu/callback")
async def feishu_verify(request: Request) -> JSONResponse:
    """Handle Feishu URL verification via GET (some configurations use GET).

    This is a secondary endpoint; primary verification is handled in the POST
    endpoint above via challenge-response.
    """
    feishu = channel_manager.get_channel("feishu")
    if feishu is None or not feishu.is_configured():
        return JSONResponse(
            status_code=200,
            content={"code": 503, "message": "Feishu channel not configured", "data": None},
        )

    return JSONResponse(content={"code": 200, "message": "Feishu callback endpoint active", "data": None})


# ======================================================================
# DingTalk Callback
# ======================================================================


@router.post("/dingtalk/callback")
async def dingtalk_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Handle DingTalk robot message callback (POST).

    This endpoint does NOT require JWT auth — it is called by
    DingTalk servers with HMAC-SHA256 signature verification.
    """
    dingtalk = channel_manager.get_channel("dingtalk")
    if dingtalk is None or not dingtalk.is_configured():
        return JSONResponse(
            status_code=200,
            content={"code": 503, "message": "DingTalk channel not configured", "data": None},
        )

    body = await request.body()

    # Verify signature
    if not dingtalk.verify_signature(request, body):
        return JSONResponse(
            status_code=200,
            content={"code": 403, "message": "signature verification failed", "data": None},
        )

    # Parse JSON payload
    try:
        import json
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return JSONResponse(
            status_code=200,
            content={"code": 400, "message": "invalid payload", "data": None},
        )

    # Handle message
    parsed = await dingtalk.handle_message(payload)

    channel_user_id = parsed.get("channel_user_id", "")
    content = parsed.get("content", "")
    session_webhook = parsed.get("session_webhook", "")

    if not channel_user_id or not content:
        return JSONResponse(content={"code": 200, "message": "ok", "data": None})

    # Route to chat_service and get reply
    reply = await channel_manager.route_message_to_chat(
        channel_name="dingtalk",
        channel_user_id=channel_user_id,
        content=content,
        db=db,
    )

    # Reply via session webhook (preferred) or proactive message
    await channel_manager.send_reply(
        channel_name="dingtalk",
        channel_user_id=channel_user_id,
        content=reply,
        session_webhook=session_webhook,
    )

    return JSONResponse(content={"code": 200, "message": "ok", "data": None})
