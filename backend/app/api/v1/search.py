"""Global search API — search across agents, knowledge bases, and conversations."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.agent import Agent
from app.models.conversation import Conversation
from app.models.knowledge import KnowledgeBase
from app.models.user import User
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/search", tags=["Search"])
logger = logging.getLogger(__name__)

MAX_RESULTS_PER_TYPE = 10


@router.get("", response_model=ApiResponse)
async def global_search(
    q: str = Query(..., min_length=1, max_length=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Search across agents, knowledge bases, and conversations by keyword."""
    pattern = f"%{q}%"
    tenant_id = current_user.tenant_id
    user_id = str(current_user.id)

    # Search agents
    agent_query = (
        select(Agent)
        .where(Agent.tenant_id == tenant_id)
        .where(Agent.is_active.is_(True))
        .where(Agent.name.ilike(pattern) | Agent.description.ilike(pattern))
        .limit(MAX_RESULTS_PER_TYPE)
    )
    agent_result = await db.execute(agent_query)
    agents = [
        {
            "id": str(a.id),
            "name": a.name,
            "description": a.description or "",
            "type": "agent",
        }
        for a in agent_result.scalars().all()
    ]

    # Search knowledge bases
    kb_query = (
        select(KnowledgeBase)
        .where(KnowledgeBase.tenant_id == tenant_id)
        .where(KnowledgeBase.name.ilike(pattern))
        .limit(MAX_RESULTS_PER_TYPE)
    )
    kb_result = await db.execute(kb_query)
    knowledge_bases = [
        {
            "id": str(kb.id),
            "name": kb.name,
            "description": kb.description or "",
            "type": "knowledge_base",
        }
        for kb in kb_result.scalars().all()
    ]

    # Search conversations
    conv_query = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .where(Conversation.title.ilike(pattern))
        .limit(MAX_RESULTS_PER_TYPE)
    )
    conv_result = await db.execute(conv_query)
    conversations = [
        {
            "id": str(c.id),
            "title": c.title or "",
            "type": "conversation",
        }
        for c in conv_result.scalars().all()
    ]

    return ApiResponse.success(
        data={
            "agents": agents,
            "knowledge_bases": knowledge_bases,
            "conversations": conversations,
        }
    )
