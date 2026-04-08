"""
3-Level Memory Manager for BridgeAI agents.

Architecture:
  Level 1: Working memory (in-process dict, session-scoped)
  Level 2: Short-term memory (Redis, 7-day TTL)
  Level 3: Long-term memory (PostgreSQL text + Milvus vectors)

High-importance facts (>= 0.7) are persisted to the DB for long-term recall.
All facts are cached in Redis for fast short-term retrieval.
When a query is provided, L3 uses Milvus cosine similarity for semantic search.
"""

import json
import logging
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentMemory
from app.rag.embeddings import get_embedding_provider
from app.rag.milvus_client import MEMORY_COLLECTION, get_milvus_client

logger = logging.getLogger(__name__)

_DEFAULT_SHORT_TERM_TTL = 7 * 86400  # 7 days in seconds
_LONG_TERM_THRESHOLD = 0.7


class MemoryManager:
    """3-level memory: working (dict) -> short-term (Redis 7d) -> long-term (Milvus + DB)."""

    def __init__(self, redis_client: aioredis.Redis, db_session: AsyncSession) -> None:
        self._working: dict[str, list[dict[str, Any]]] = {}
        self._redis = redis_client
        self._db = db_session
        self._embedding_provider = get_embedding_provider()

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

        # Level 3: Long-term (DB + Milvus) -- only high-importance facts
        if importance >= _LONG_TERM_THRESHOLD:
            try:
                # Generate embedding for the fact
                embedding = await self._embedding_provider.embed_query(fact)

                # Store text metadata in PostgreSQL (no embedding column)
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

                # Store vector in Milvus
                milvus = get_milvus_client()
                milvus.upsert(
                    collection_name=MEMORY_COLLECTION,
                    data=[
                        {
                            "memory_id": str(mem.id),
                            "tenant_id": tenant_id,
                            "agent_id": agent_id,
                            "embedding": embedding,
                        }
                    ],
                )
            except Exception as e:
                logger.warning("DB/Milvus memory store failed: %s", e)

    async def retrieve(
        self,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        query: str | None = None,
        top_k: int = 5,
    ) -> list[str]:
        """Retrieve relevant memories from all 3 levels, deduplicated.

        When a query is provided, L3 uses Milvus cosine similarity for
        semantic search instead of simple importance-based ordering.
        """
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

        # Level 3: Milvus + DB long-term
        if query:
            try:
                # Generate embedding for the query
                query_embedding = await self._embedding_provider.embed_query(query)

                # Search in Milvus with tenant_id + agent_id filter
                milvus = get_milvus_client()
                milvus_results = milvus.search(
                    collection_name=MEMORY_COLLECTION,
                    data=[query_embedding],
                    filter=f'tenant_id == "{tenant_id}" && agent_id == "{agent_id}"',
                    limit=top_k,
                    output_fields=["memory_id"],
                )

                memory_ids: list[str] = []
                if milvus_results and milvus_results[0]:
                    memory_ids = [
                        hit["entity"]["memory_id"] for hit in milvus_results[0]
                    ]

                if memory_ids:
                    # Query PostgreSQL for content
                    rows = await self._db.execute(
                        text(
                            "SELECT content FROM agent_memories "
                            "WHERE id = ANY(:ids)"
                        ),
                        {"ids": memory_ids},
                    )
                    for row in rows:
                        if row[0] not in results:
                            results.append(row[0])
                else:
                    # Fallback: no vectors stored yet, use importance ordering
                    rows = await self._db.execute(
                        text(
                            "SELECT content FROM agent_memories "
                            "WHERE tenant_id = :tid AND user_id = :uid "
                            "AND agent_id = :aid "
                            "ORDER BY importance DESC, created_at DESC "
                            "LIMIT :k"
                        ),
                        {
                            "tid": tenant_id,
                            "uid": user_id,
                            "aid": agent_id,
                            "k": top_k,
                        },
                    )
                    for row in rows:
                        if row[0] not in results:
                            results.append(row[0])
            except Exception as e:
                logger.warning("Milvus/DB memory retrieve failed: %s", e)

        return results[:top_k]

    def clear_working(self, tenant_id: str, user_id: str, agent_id: str) -> None:
        """Clear working memory for a given session key."""
        key = f"{tenant_id}:{user_id}:{agent_id}"
        self._working.pop(key, None)
