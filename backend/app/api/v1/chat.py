"""Chat API endpoint — supports both streaming SSE and non-streaming JSON responses."""

import json
import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.core.security import get_current_user
from app.engine.feedback_loop import store_fewshot_example
from app.models.conversation import Conversation, Message, MessageRating
from app.models.user import User
from app.rag.parsers.factory import get_parser
from app.schemas.billing import RateRequest
from app.schemas.chat import ChatRequest
from app.schemas.common import ApiResponse, PageResponse
from app.services.chat_service import process_chat, process_chat_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


async def _safe_stream(
    request: ChatRequest,
    db: AsyncSession,
    user_id: str,
    tenant_id: str | None = None,
):
    """Wrap streaming generator with top-level error boundary.

    If an unhandled exception escapes the pipeline, the client receives
    a final ``error`` + ``done`` event instead of a broken connection.
    """
    try:
        async for chunk in process_chat(request, db, user_id=user_id, tenant_id=tenant_id):
            yield chunk
    except Exception as e:
        logger.error("Streaming pipeline error: %s", e, exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.post("/completions", response_model=None)
async def chat_completions(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse | JSONResponse:
    """
    Chat completions endpoint.

    Accepts both ``messages`` array format and simple ``message`` string.
    Supports ``stream: true`` (SSE) and ``stream: false`` (JSON).

    SSE event types:
      - ``meta``       — first event, carries ``conversation_id``
      - ``content``    — text chunk
      - ``tool_call``  — tool invocation
      - ``tool_result``— tool execution result
      - ``analysis``   — structured intent/emotion data
      - ``error``      — error message
      - ``done``       — stream complete
    """
    user_id = str(current_user.id)
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None

    if request.stream:
        return StreamingResponse(
            _safe_stream(request, db, user_id=user_id, tenant_id=tenant_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming: collect full response
    try:
        result = await process_chat_sync(request, db, user_id=user_id, tenant_id=tenant_id)
        return JSONResponse(
            content={"code": 200, "message": "success", "data": result},
        )
    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": str(e), "data": None},
        )


@router.post("/messages/{message_id}/rate", response_model=ApiResponse)
async def rate_message(
    message_id: str,
    request: RateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """为消息评分，高评分对话自动进入 few-shot 学习池。"""
    if request.rating < 1 or request.rating > 5:
        return ApiResponse.error(code=400, message="评分范围为 1-5")

    # Validate UUID format
    import uuid as _uuid
    try:
        msg_uuid = _uuid.UUID(message_id)
    except ValueError:
        raise NotFoundException(message="消息不存在")

    # 查找目标消息（必须是 assistant 消息）
    result = await db.execute(
        select(Message).where(Message.id == msg_uuid)
    )
    target_msg = result.scalar_one_or_none()
    if not target_msg:
        raise NotFoundException(message="消息不存在")

    # 租户隔离检查
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None
    if tenant_id and target_msg.tenant_id and str(target_msg.tenant_id) != tenant_id:
        return ApiResponse.error(code=403, message="无权操作该消息")

    # 保存评分记录
    rating_record = MessageRating(
        message_id=target_msg.id,
        user_id=current_user.id,
        rating=request.rating,
        feedback=request.feedback,
    )
    db.add(rating_record)
    await db.flush()

    # 如果评分 >= 4，查找对应的 user 消息并存入 few-shot
    if request.rating >= 4 and target_msg.role == "assistant":
        # 查找这条 assistant 消息之前最近的 user 消息
        user_msg_result = await db.execute(
            select(Message)
            .where(
                Message.conversation_id == target_msg.conversation_id,
                Message.role == "user",
                Message.created_at < target_msg.created_at,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        user_msg = user_msg_result.scalar_one_or_none()

        if user_msg and target_msg.tenant_id:
            # 获取 conversation 的 agent_id
            from app.models.conversation import Conversation
            conv_result = await db.execute(
                select(Conversation).where(Conversation.id == target_msg.conversation_id)
            )
            conv = conv_result.scalar_one_or_none()
            agent_id = str(conv.agent_id) if conv and conv.agent_id else "default"

            await store_fewshot_example(
                tenant_id=str(target_msg.tenant_id),
                agent_id=agent_id,
                user_message=user_msg.content,
                ai_response=target_msg.content,
                rating=request.rating,
            )

    return ApiResponse.success(message="评分成功")


@router.get("/conversations", response_model=ApiResponse[PageResponse])
async def list_conversations(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List conversations for the current user."""
    user_id = str(current_user.id)
    query = select(Conversation).where(Conversation.user_id == user_id)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        query.offset((page - 1) * size).limit(size).order_by(Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()
    items = []
    for conv in conversations:
        # Count messages for this conversation
        msg_count_q = select(func.count()).select_from(
            select(Message.id).where(Message.conversation_id == conv.id).subquery()
        )
        msg_count = (await db.execute(msg_count_q)).scalar() or 0

        agent_name = conv.agent.name if conv.agent else "助手"
        items.append({
            "id": str(conv.id),
            "title": conv.title or "新的对话",
            "agentId": str(conv.agent_id) if conv.agent_id else "",
            "agentName": agent_name,
            "messageCount": msg_count,
            "createdAt": conv.created_at.isoformat() if conv.created_at else "",
            "updatedAt": conv.updated_at.isoformat() if conv.updated_at else "",
        })

    pages = (total + size - 1) // size
    return ApiResponse.success(
        data=PageResponse(items=items, total=total, page=page, size=size, pages=pages)
    )


@router.get("/conversations/{conversation_id}/messages", response_model=ApiResponse[PageResponse])
async def list_messages(
    conversation_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List messages for a conversation."""
    # Verify conversation belongs to user
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == str(current_user.id),
        )
    )
    conv = conv_result.scalar_one_or_none()
    if conv is None:
        raise NotFoundException(message="Conversation not found")

    query = select(Message).where(Message.conversation_id == conversation_id)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        query.offset((page - 1) * size).limit(size).order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    items = [
        {
            "id": str(msg.id),
            "conversationId": str(msg.conversation_id),
            "role": msg.role,
            "content": msg.content,
            "createdAt": msg.created_at.isoformat() if msg.created_at else "",
        }
        for msg in messages
    ]

    pages = (total + size - 1) // size
    return ApiResponse.success(
        data=PageResponse(items=items, total=total, page=page, size=size, pages=pages)
    )


@router.delete("/conversations/{conversation_id}", response_model=ApiResponse)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Delete a conversation."""
    import uuid as _uuid
    try:
        _uuid.UUID(conversation_id)
    except ValueError:
        raise NotFoundException(message="Conversation not found")

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == str(current_user.id),
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise NotFoundException(message="Conversation not found")

    await db.delete(conv)
    await db.flush()
    return ApiResponse.success(message="Conversation deleted")


# Max file size for chat upload: 10 MB
_MAX_UPLOAD_SIZE = 10 * 1024 * 1024


@router.post("/upload", response_model=ApiResponse)
async def upload_file_for_chat(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Upload a file and return its parsed text content for chat context.

    Supports the same file types as the knowledge base parser:
    .txt, .pdf, .docx, .xlsx, .md, .csv, .json, .xml, .yaml, etc.
    """
    filename = file.filename or "unknown"
    content_bytes = await file.read()

    if len(content_bytes) > _MAX_UPLOAD_SIZE:
        return ApiResponse.error(code=400, message="文件大小不能超过 10MB")

    if len(content_bytes) == 0:
        return ApiResponse.error(code=400, message="文件内容为空")

    # Determine extension
    file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    suffix = f".{file_ext}" if file_ext else ""

    # Save to temp file for parser
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=tempfile.gettempdir())
    try:
        tmp.write(content_bytes)
        tmp.close()

        parser = get_parser(filename)
        parsed_text = parser.parse(tmp.name)
    except Exception as e:
        logger.error("Failed to parse uploaded file %s: %s", filename, e)
        return ApiResponse.error(code=400, message=f"文件解析失败: {str(e)}")
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    # Truncate very large parsed text to avoid overwhelming context
    max_chars = 50_000
    truncated = len(parsed_text) > max_chars
    if truncated:
        parsed_text = parsed_text[:max_chars]

    return ApiResponse.success(
        data={
            "filename": filename,
            "fileSize": len(content_bytes),
            "content": parsed_text,
            "truncated": truncated,
        }
    )
