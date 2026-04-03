"""
3-Level Memory Manager for BridgeAI agents.

Architecture:
  Level 1: Working memory (in-process dict, session-scoped)
  Level 2: Short-term memory (Redis, 7-day TTL)
  Level 3: Long-term memory (PostgreSQL agent_memories table)

High-importance facts (>= 0.7) are persisted to the DB for long-term recall.
All facts are cached in Redis for fast short-term retrieval.
"""

import json
import logging
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentMemory

logger = logging.getLogger(__name__)

_DEFAULT_SHORT_TERM_TTL = 7 * 86400  # 7 days in seconds
_LONG_TERM_THRESHOLD = 0.7


class MemoryManager:
    """3-level memory: working (dict) -> short-term (Redis 7d) -> long-term (DB)."""

    def __init__(self, redis_client: aioredis.Redis, db_session: AsyncSession) -> None:
        self._working: dict[str, list[dict[str, Any]]] = {}
        self._redis = redis_client
        self._db = db_session

    async def store(
        self,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        fact: str,
        importance: float = 0.5,
    ) -> None:
        """Store a memory fact at appropriate level based on importance."""
        key = f"{tenant_id}:{user_id}:{agent_id}"
        entry = {"fact": fact, "importance": importance}

        # Level 1: Working memory (current session)
        if key not in self._working:
            self._working[key] = []
        self._working[key].append(entry)

        # Level 2: Short-term (Redis, 7-day TTL)
        redis_key = f"memory:{key}"
        try:
            await self._redis.lpush(redis_key, json.dumps(entry, ensure_ascii=False))
            await self._redis.expire(redis_key, _DEFAULT_SHORT_TERM_TTL)
        except Exception as e:
            logger.warning("Redis memory store failed: %s", e)

        # Level 3: Long-term (DB agent_memories table) -- only high-importance facts
        if importance >= _LONG_TERM_THRESHOLD:
            try:
                mem = AgentMemory(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    agent_id=agent_id,
                    memory_type="fact",
                    content=fact,
                    importance=importance,
                )
                self._db.add(mem)
                await self._db.flush()
            except Exception as e:
                logger.warning("DB memory store failed: %s", e)

    async def retrieve(
        self,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        query: str | None = None,
        top_k: int = 5,
    ) -> list[str]:
        """Retrieve relevant memories from all 3 levels, deduplicated."""
        results: list[str] = []
        key = f"{tenant_id}:{user_id}:{agent_id}"

        # Level 1: Working memory (most recent 5)
        if key in self._working:
            for m in self._working[key][-5:]:
                if m["fact"] not in results:
                    results.append(m["fact"])

        # Level 2: Redis short-term (last 10 entries)
        redis_key = f"memory:{key}"
        try:
            cached = await self._redis.lrange(redis_key, 0, 9)
            for item in cached:
                data = json.loads(item)
                if data["fact"] not in results:
                    results.append(data["fact"])
        except Exception as e:
            logger.warning("Redis memory retrieve failed: %s", e)

        # Level 3: DB long-term (ordered by importance + recency)
        if query:
            try:
                rows = await self._db.execute(
                    text(
                        "SELECT content FROM agent_memories "
                        "WHERE tenant_id = :tid AND user_id = :uid "
                        "AND agent_id = :aid "
                        "ORDER BY importance DESC, created_at DESC "
                        "LIMIT :k"
                    ),
                    {"tid": tenant_id, "uid": user_id, "aid": agent_id, "k": top_k},
                )
                for row in rows:
                    if row[0] not in results:
                        results.append(row[0])
            except Exception as e:
                logger.warning("DB memory retrieve failed: %s", e)

        return results[:top_k]

    def clear_working(self, tenant_id: str, user_id: str, agent_id: str) -> None:
        """Clear working memory for a given session key."""
        key = f"{tenant_id}:{user_id}:{agent_id}"
        self._working.pop(key, None)
