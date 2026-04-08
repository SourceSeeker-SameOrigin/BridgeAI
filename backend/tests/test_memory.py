"""Tests for app.agents.memory — 3-level memory manager."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.memory import MemoryManager, _DEFAULT_SHORT_TERM_TTL, _LONG_TERM_THRESHOLD


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.lpush = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.lrange = AsyncMock(return_value=[])
    return redis


@pytest.fixture
def mock_db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def manager(mock_redis: AsyncMock, mock_db: AsyncMock) -> MemoryManager:
    return MemoryManager(redis_client=mock_redis, db_session=mock_db)


# ---------------------------------------------------------------------------
# Level 1: Working Memory
# ---------------------------------------------------------------------------

class TestWorkingMemory:
    """In-process dict, session-scoped memory."""

    @pytest.mark.asyncio
    async def test_store_and_retrieve_working_memory(
        self, manager: MemoryManager, mock_redis: AsyncMock
    ) -> None:
        mock_redis.lrange.return_value = []
        await manager.store("t1", "u1", "a1", "Python is a language", importance=0.3)
        result = await manager.retrieve("t1", "u1", "a1")
        assert "Python is a language" in result

    @pytest.mark.asyncio
    async def test_multiple_facts_stored(
        self, manager: MemoryManager, mock_redis: AsyncMock
    ) -> None:
        mock_redis.lrange.return_value = []
        await manager.store("t1", "u1", "a1", "fact1", importance=0.3)
        await manager.store("t1", "u1", "a1", "fact2", importance=0.3)
        result = await manager.retrieve("t1", "u1", "a1")
        assert "fact1" in result
        assert "fact2" in result

    @pytest.mark.asyncio
    async def test_clear_working_memory(
        self, manager: MemoryManager, mock_redis: AsyncMock
    ) -> None:
        mock_redis.lrange.return_value = []
        await manager.store("t1", "u1", "a1", "temp fact", importance=0.3)
        manager.clear_working("t1", "u1", "a1")
        result = await manager.retrieve("t1", "u1", "a1")
        assert "temp fact" not in result

    def test_clear_nonexistent_key_no_error(self, manager: MemoryManager) -> None:
        # Should not raise
        manager.clear_working("nonexistent", "user", "agent")

    @pytest.mark.asyncio
    async def test_working_memory_limited_to_5(
        self, manager: MemoryManager, mock_redis: AsyncMock
    ) -> None:
        mock_redis.lrange.return_value = []
        for i in range(10):
            await manager.store("t1", "u1", "a1", f"fact{i}", importance=0.3)
        result = await manager.retrieve("t1", "u1", "a1")
        # Working memory returns last 5 entries
        assert "fact5" in result
        assert "fact9" in result


# ---------------------------------------------------------------------------
# Level 2: Short-term Memory (Redis)
# ---------------------------------------------------------------------------

class TestShortTermMemory:
    """Redis-backed short-term memory with 7-day TTL."""

    @pytest.mark.asyncio
    async def test_store_pushes_to_redis(
        self, manager: MemoryManager, mock_redis: AsyncMock
    ) -> None:
        await manager.store("t1", "u1", "a1", "redis fact", importance=0.3)
        mock_redis.lpush.assert_called_once()
        call_args = mock_redis.lpush.call_args[0]
        assert call_args[0] == "memory:t1:u1:a1"
        data = json.loads(call_args[1])
        assert data["fact"] == "redis fact"
        assert data["importance"] == 0.3

    @pytest.mark.asyncio
    async def test_ttl_set_on_redis_key(
        self, manager: MemoryManager, mock_redis: AsyncMock
    ) -> None:
        await manager.store("t1", "u1", "a1", "fact", importance=0.3)
        mock_redis.expire.assert_called_once_with(
            "memory:t1:u1:a1", _DEFAULT_SHORT_TERM_TTL,
        )

    @pytest.mark.asyncio
    async def test_retrieve_from_redis(
        self, manager: MemoryManager, mock_redis: AsyncMock
    ) -> None:
        mock_redis.lrange.return_value = [
            json.dumps({"fact": "cached_fact", "importance": 0.5}),
        ]
        result = await manager.retrieve("t1", "u1", "a1")
        assert "cached_fact" in result

    @pytest.mark.asyncio
    async def test_redis_error_on_store_does_not_raise(
        self, mock_db: AsyncMock
    ) -> None:
        failing_redis = AsyncMock()
        failing_redis.lpush = AsyncMock(side_effect=ConnectionError("down"))
        failing_redis.expire = AsyncMock()
        mgr = MemoryManager(redis_client=failing_redis, db_session=mock_db)
        # Should not raise, just log warning
        await mgr.store("t1", "u1", "a1", "fact", importance=0.3)

    @pytest.mark.asyncio
    async def test_redis_error_on_retrieve_does_not_raise(
        self, mock_db: AsyncMock
    ) -> None:
        failing_redis = AsyncMock()
        failing_redis.lrange = AsyncMock(side_effect=ConnectionError("down"))
        mgr = MemoryManager(redis_client=failing_redis, db_session=mock_db)
        result = await mgr.retrieve("t1", "u1", "a1")
        # Should return empty or only working memory
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_dedup_between_working_and_redis(
        self, manager: MemoryManager, mock_redis: AsyncMock
    ) -> None:
        # Store a fact in working memory
        await manager.store("t1", "u1", "a1", "shared_fact", importance=0.3)
        # Also return same fact from Redis
        mock_redis.lrange.return_value = [
            json.dumps({"fact": "shared_fact", "importance": 0.5}),
        ]
        result = await manager.retrieve("t1", "u1", "a1")
        # Should appear only once
        assert result.count("shared_fact") == 1


# ---------------------------------------------------------------------------
# Level 3: Long-term Memory (DB) — importance threshold
# ---------------------------------------------------------------------------

class TestLongTermMemory:
    """High importance facts (>= 0.7) persisted to DB."""

    @pytest.mark.asyncio
    async def test_high_importance_stored_to_db(
        self, manager: MemoryManager, mock_db: AsyncMock
    ) -> None:
        await manager.store("t1", "u1", "a1", "important fact", importance=0.8)
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_exact_threshold_stored_to_db(
        self, manager: MemoryManager, mock_db: AsyncMock
    ) -> None:
        await manager.store("t1", "u1", "a1", "threshold fact", importance=0.7)
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_low_importance_not_stored_to_db(
        self, manager: MemoryManager, mock_db: AsyncMock
    ) -> None:
        await manager.store("t1", "u1", "a1", "trivial fact", importance=0.5)
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_below_threshold_not_stored(
        self, manager: MemoryManager, mock_db: AsyncMock
    ) -> None:
        await manager.store("t1", "u1", "a1", "low fact", importance=0.69)
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_error_on_store_does_not_raise(
        self, mock_redis: AsyncMock
    ) -> None:
        failing_db = AsyncMock()
        failing_db.add = MagicMock(side_effect=Exception("DB error"))
        failing_db.flush = AsyncMock()
        mgr = MemoryManager(redis_client=mock_redis, db_session=failing_db)
        # Should not raise
        await mgr.store("t1", "u1", "a1", "fact", importance=0.9)

    @pytest.mark.asyncio
    async def test_retrieve_with_query_hits_db(
        self, manager: MemoryManager, mock_redis: AsyncMock, mock_db: AsyncMock
    ) -> None:
        mock_redis.lrange.return_value = []
        # Mock DB result
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([("db_fact",)]))
        mock_db.execute.return_value = mock_result

        result = await manager.retrieve("t1", "u1", "a1", query="search term")
        assert "db_fact" in result
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_without_query_skips_db(
        self, manager: MemoryManager, mock_redis: AsyncMock, mock_db: AsyncMock
    ) -> None:
        mock_redis.lrange.return_value = []
        result = await manager.retrieve("t1", "u1", "a1")
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_retrieve_top_k_limits_results(
        self, manager: MemoryManager, mock_redis: AsyncMock
    ) -> None:
        # Store 10 facts in working memory
        for i in range(10):
            await manager.store("t1", "u1", "a1", f"fact{i}", importance=0.3)
        mock_redis.lrange.return_value = []
        result = await manager.retrieve("t1", "u1", "a1", top_k=3)
        assert len(result) <= 3
