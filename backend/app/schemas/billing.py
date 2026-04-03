from typing import Any, Dict, Optional

from pydantic import BaseModel


class UsageSummary(BaseModel):
    """当月用量汇总"""
    monthly_calls: int = 0
    monthly_tokens: int = 0
    chat_calls: int = 0
    mcp_calls: int = 0
    rag_calls: int = 0
    chat_tokens: int = 0


class PlanInfo(BaseModel):
    """当前套餐信息"""
    plan: str = "free"
    monthly_calls_limit: int = 100
    monthly_tokens_limit: int = 50000
    monthly_calls_used: int = 0
    monthly_tokens_used: int = 0
    calls_remaining: int = 100
    tokens_remaining: int = 50000


class RateRequest(BaseModel):
    rating: int  # 1-5
    feedback: Optional[str] = None
