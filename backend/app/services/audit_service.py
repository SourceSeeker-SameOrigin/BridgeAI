"""Audit Service — 统一审计日志记录与查询。"""

import csv
import io
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.schemas.common import PageResponse

logger = logging.getLogger(__name__)


class AuditService:
    """提供统一的审计日志记录接口，支持 chat / mcp / plugin / rag 等类型。"""

    async def log_mcp_call(
        self,
        db: AsyncSession,
        tenant_id: str,
        connector_id: str,
        agent_id: Optional[str],
        user_id: Optional[str],
        action: str,
        request_payload: Optional[dict[str, Any]],
        response_payload: Optional[dict[str, Any]],
        status: str,
        duration_ms: int,
        error_message: Optional[str] = None,
    ) -> None:
        """记录 MCP 工具调用审计日志。"""
        try:
            audit = AuditLog(
                tenant_id=uuid.UUID(tenant_id),
                user_id=uuid.UUID(user_id) if user_id else None,
                agent_id=uuid.UUID(agent_id) if agent_id else None,
                connector_id=uuid.UUID(connector_id),
                log_type="mcp",
                action=action,
                request_payload=request_payload,
                response_payload=response_payload,
                status=status,
                error_message=error_message,
                duration_ms=duration_ms,
            )
            db.add(audit)
            await db.flush()
        except Exception as e:
            logger.warning("Failed to record MCP audit log: %s", e)

    async def log_chat(
        self,
        db: AsyncSession,
        tenant_id: str,
        user_id: str,
        agent_id: Optional[str],
        conversation_id: str,
        model_used: str,
        tokens_in: int,
        tokens_out: int,
        duration_ms: int,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> None:
        """记录 Chat 对话审计日志。"""
        try:
            audit = AuditLog(
                tenant_id=uuid.UUID(tenant_id),
                user_id=uuid.UUID(user_id),
                agent_id=uuid.UUID(agent_id) if agent_id else None,
                conversation_id=uuid.UUID(conversation_id),
                log_type="chat",
                action="chat_completion",
                status=status,
                error_message=error_message,
                duration_ms=duration_ms,
                model_used=model_used,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
            db.add(audit)
            await db.flush()
        except Exception as e:
            logger.warning("Failed to record chat audit log: %s", e)

    async def log_plugin_call(
        self,
        db: AsyncSession,
        tenant_id: str,
        user_id: Optional[str],
        plugin_name: str,
        tool_name: str,
        status: str,
        duration_ms: int,
        error_message: Optional[str] = None,
    ) -> None:
        """记录插件调用审计日志。"""
        try:
            audit = AuditLog(
                tenant_id=uuid.UUID(tenant_id),
                user_id=uuid.UUID(user_id) if user_id else None,
                log_type="plugin",
                action=f"{plugin_name}:{tool_name}",
                status=status,
                duration_ms=duration_ms,
                error_message=error_message,
            )
            db.add(audit)
            await db.flush()
        except Exception as e:
            logger.warning("Failed to record plugin audit log: %s", e)

    async def log_rag_query(
        self,
        db: AsyncSession,
        tenant_id: str,
        user_id: Optional[str],
        agent_id: Optional[str],
        knowledge_base_id: str,
        query: str,
        results_count: int,
        duration_ms: int,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> None:
        """记录 RAG 查询审计日志。"""
        try:
            audit = AuditLog(
                tenant_id=uuid.UUID(tenant_id),
                user_id=uuid.UUID(user_id) if user_id else None,
                agent_id=uuid.UUID(agent_id) if agent_id else None,
                log_type="rag",
                action="rag_search",
                request_payload={"query": query[:500]},
                response_payload={"results_count": results_count},
                status=status,
                error_message=error_message,
                duration_ms=duration_ms,
            )
            db.add(audit)
            await db.flush()
        except Exception as e:
            logger.warning("Failed to record RAG audit log: %s", e)

    async def get_audit_logs(
        self,
        db: AsyncSession,
        tenant_id: str,
        page: int = 1,
        size: int = 20,
        log_type: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None,
        action: Optional[str] = None,
    ) -> PageResponse:
        """分页查询审计日志，支持多种过滤条件。"""
        query = select(AuditLog).where(AuditLog.tenant_id == uuid.UUID(tenant_id))
        count_query = select(func.count(AuditLog.id)).where(AuditLog.tenant_id == uuid.UUID(tenant_id))

        if log_type:
            query = query.where(AuditLog.log_type == log_type)
            count_query = count_query.where(AuditLog.log_type == log_type)
        if user_id:
            query = query.where(AuditLog.user_id == uuid.UUID(user_id))
            count_query = count_query.where(AuditLog.user_id == uuid.UUID(user_id))
        if status:
            query = query.where(AuditLog.status == status)
            count_query = count_query.where(AuditLog.status == status)
        if action:
            query = query.where(AuditLog.action.ilike(f"%{action}%"))
            count_query = count_query.where(AuditLog.action.ilike(f"%{action}%"))
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                query = query.where(AuditLog.created_at >= start_dt)
                count_query = count_query.where(AuditLog.created_at >= start_dt)
            except ValueError:
                pass
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
                query = query.where(AuditLog.created_at <= end_dt)
                count_query = count_query.where(AuditLog.created_at <= end_dt)
            except ValueError:
                pass

        # Total count
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated data
        offset = (page - 1) * size
        query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(size)
        result = await db.execute(query)
        logs = result.scalars().all()

        items = [
            {
                "id": str(log.id),
                "tenant_id": str(log.tenant_id),
                "connector_id": str(log.connector_id) if log.connector_id else None,
                "user_id": str(log.user_id) if log.user_id else None,
                "agent_id": str(log.agent_id) if log.agent_id else None,
                "log_type": log.log_type,
                "action": log.action,
                "request_payload": log.request_payload,
                "response_payload": log.response_payload,
                "status": log.status,
                "error_message": log.error_message,
                "duration_ms": log.duration_ms,
                "model_used": log.model_used,
                "tokens_in": log.tokens_in,
                "tokens_out": log.tokens_out,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]

        pages = (total + size - 1) // size if size > 0 else 0

        return PageResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    async def export_csv(
        self,
        db: AsyncSession,
        tenant_id: str,
        log_type: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> str:
        """导出审计日志为 CSV 格式字符串。"""
        query = select(AuditLog).where(AuditLog.tenant_id == uuid.UUID(tenant_id))

        if log_type:
            query = query.where(AuditLog.log_type == log_type)
        if user_id:
            query = query.where(AuditLog.user_id == uuid.UUID(user_id))
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                query = query.where(AuditLog.created_at >= start_dt)
            except ValueError:
                pass
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
                query = query.where(AuditLog.created_at <= end_dt)
            except ValueError:
                pass

        query = query.order_by(AuditLog.created_at.desc()).limit(10000)
        result = await db.execute(query)
        logs = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "tenant_id", "user_id", "log_type", "action",
            "status", "error_message", "duration_ms", "model_used",
            "tokens_in", "tokens_out", "created_at",
        ])
        for log in logs:
            writer.writerow([
                str(log.id),
                str(log.tenant_id),
                str(log.user_id) if log.user_id else "",
                log.log_type,
                log.action,
                log.status,
                log.error_message or "",
                log.duration_ms or "",
                log.model_used or "",
                log.tokens_in or "",
                log.tokens_out or "",
                log.created_at.isoformat() if log.created_at else "",
            ])

        return output.getvalue()


# Global singleton
audit_service = AuditService()
