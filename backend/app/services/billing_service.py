"""Billing Service — 用量计费与配额控制。"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plugin import UsageRecord
from app.models.user import Tenant
from app.schemas.billing import PlanInfo, UsageSummary

logger = logging.getLogger(__name__)

# 套餐限制配置
PLAN_LIMITS: dict[str, dict[str, int]] = {
    "free": {"monthly_calls": 100, "monthly_tokens": 50000},
    "pro": {"monthly_calls": 5000, "monthly_tokens": 1000000},
    "enterprise": {"monthly_calls": 50000, "monthly_tokens": 10000000},
}


class BillingService:
    """用量计费服务：记录用量、查询汇总、检查配额。"""

    async def record_chat_usage(
        self,
        db: AsyncSession,
        tenant_id: str,
        user_id: str,
        agent_id: Optional[str],
        model: str,
        tokens_in: int,
        tokens_out: int,
    ) -> None:
        """记录一次 Chat 调用的用量。"""
        try:
            total_tokens = tokens_in + tokens_out
            record = UsageRecord(
                tenant_id=uuid.UUID(tenant_id),
                user_id=uuid.UUID(user_id),
                agent_id=uuid.UUID(agent_id) if agent_id else None,
                resource_type="chat",
                quantity=total_tokens,
                unit="tokens",
                model=model,
                metadata_={
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                },
            )
            db.add(record)
            await db.flush()
        except Exception as e:
            logger.warning("Failed to record chat usage: %s", e)

    async def record_mcp_usage(
        self,
        db: AsyncSession,
        tenant_id: str,
        user_id: Optional[str],
        agent_id: Optional[str],
        connector_id: str,
        tool_name: str,
    ) -> None:
        """记录一次 MCP 工具调用的用量（1 unit）。"""
        try:
            record = UsageRecord(
                tenant_id=uuid.UUID(tenant_id),
                user_id=uuid.UUID(user_id) if user_id else None,
                agent_id=uuid.UUID(agent_id) if agent_id else None,
                resource_type="mcp",
                quantity=1,
                unit="calls",
                metadata_={
                    "connector_id": connector_id,
                    "tool_name": tool_name,
                },
            )
            db.add(record)
            await db.flush()
        except Exception as e:
            logger.warning("Failed to record MCP usage: %s", e)

    async def record_rag_usage(
        self,
        db: AsyncSession,
        tenant_id: str,
        user_id: Optional[str],
        agent_id: Optional[str],
        knowledge_base_id: str,
    ) -> None:
        """记录一次 RAG 查询的用量（1 unit）。"""
        try:
            record = UsageRecord(
                tenant_id=uuid.UUID(tenant_id),
                user_id=uuid.UUID(user_id) if user_id else None,
                agent_id=uuid.UUID(agent_id) if agent_id else None,
                resource_type="rag",
                quantity=1,
                unit="calls",
                metadata_={"knowledge_base_id": knowledge_base_id},
            )
            db.add(record)
            await db.flush()
        except Exception as e:
            logger.warning("Failed to record RAG usage: %s", e)

    async def get_monthly_usage(
        self,
        db: AsyncSession,
        tenant_id: str,
    ) -> UsageSummary:
        """查询当月用量汇总。"""
        now = datetime.now(timezone.utc)
        tid = uuid.UUID(tenant_id)

        # 查询当月各类型的调用次数
        count_query = (
            select(
                UsageRecord.resource_type,
                func.count(UsageRecord.id).label("call_count"),
                func.coalesce(func.sum(UsageRecord.quantity), 0).label("total_quantity"),
            )
            .where(
                UsageRecord.tenant_id == tid,
                extract("year", UsageRecord.recorded_at) == now.year,
                extract("month", UsageRecord.recorded_at) == now.month,
            )
            .group_by(UsageRecord.resource_type)
        )

        result = await db.execute(count_query)
        rows = result.all()

        chat_calls = 0
        mcp_calls = 0
        rag_calls = 0
        chat_tokens = 0

        for row in rows:
            resource_type = row[0]
            call_count = int(row[1])
            total_quantity = int(row[2])

            if resource_type == "chat":
                chat_calls = call_count
                chat_tokens = total_quantity
            elif resource_type == "mcp":
                mcp_calls = call_count
            elif resource_type == "rag":
                rag_calls = call_count

        monthly_calls = chat_calls + mcp_calls + rag_calls

        return UsageSummary(
            monthly_calls=monthly_calls,
            monthly_tokens=chat_tokens,
            chat_calls=chat_calls,
            mcp_calls=mcp_calls,
            rag_calls=rag_calls,
            chat_tokens=chat_tokens,
        )

    async def get_plan_info(
        self,
        db: AsyncSession,
        tenant_id: str,
    ) -> PlanInfo:
        """获取当前套餐信息和剩余配额。"""
        # 获取租户的套餐
        tid = uuid.UUID(tenant_id)
        result = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = result.scalar_one_or_none()

        plan = tenant.plan if tenant else "free"
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])

        usage = await self.get_monthly_usage(db, tenant_id)

        calls_remaining = max(0, limits["monthly_calls"] - usage.monthly_calls)
        tokens_remaining = max(0, limits["monthly_tokens"] - usage.monthly_tokens)

        return PlanInfo(
            plan=plan,
            monthly_calls_limit=limits["monthly_calls"],
            monthly_tokens_limit=limits["monthly_tokens"],
            monthly_calls_used=usage.monthly_calls,
            monthly_tokens_used=usage.monthly_tokens,
            calls_remaining=calls_remaining,
            tokens_remaining=tokens_remaining,
        )

    async def check_quota(
        self,
        db: AsyncSession,
        tenant_id: str,
    ) -> tuple[bool, str]:
        """检查租户是否还有剩余配额。

        Returns:
            (is_allowed, error_message)
        """
        plan_info = await self.get_plan_info(db, tenant_id)

        if plan_info.calls_remaining <= 0:
            return False, "已超出当月免费额度（调用次数），请升级套餐"
        if plan_info.tokens_remaining <= 0:
            return False, "已超出当月免费额度（Token 数量），请升级套餐"

        return True, ""


# Global singleton
billing_service = BillingService()
