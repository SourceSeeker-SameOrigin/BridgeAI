"""Tests for app.engine.feedback_loop — few-shot example storage/retrieval."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engine.feedback_loop import (
    _FEWSHOT_MAX_EXAMPLES,
    _FEWSHOT_MIN_RATING,
    _FEWSHOT_TTL_SECONDS,
    _build_key,
    load_fewshot_examples,
    store_fewshot_example,
)


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.zadd = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.zcard = AsyncMock(return_value=5)
    redis.zrevrange = AsyncMock(return_value=[])
    redis.zremrangebyrank = AsyncMock(return_value=0)
    return redis


class TestBuildKey:
    def test_key_format(self) -> None:
        key = _build_key("tenant1", "agent1")
        assert key == "fewshot:tenant1:agent1"


class TestStoreFewshotExample:
    """Test storing high-rated conversations as few-shot examples."""

    @pytest.mark.asyncio
    async def test_store_high_rating(self, mock_redis: AsyncMock) -> None:
        with patch("app.engine.feedback_loop.get_redis", return_value=mock_redis):
            result = await store_fewshot_example(
                tenant_id="t1",
                agent_id="a1",
                user_message="What is AI?",
                ai_response="AI is artificial intelligence.",
                rating=5,
            )
            assert result is True
            mock_redis.zadd.assert_called_once()
            mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_rating_4_accepted(self, mock_redis: AsyncMock) -> None:
        with patch("app.engine.feedback_loop.get_redis", return_value=mock_redis):
            result = await store_fewshot_example(
                tenant_id="t1",
                agent_id="a1",
                user_message="Q",
                ai_response="A",
                rating=4,
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_skip_low_rating(self, mock_redis: AsyncMock) -> None:
        result = await store_fewshot_example(
            tenant_id="t1",
            agent_id="a1",
            user_message="Q",
            ai_response="A",
            rating=3,
        )
        assert result is False
        # Redis should never be called
        mock_redis.zadd.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_rating_1(self, mock_redis: AsyncMock) -> None:
        result = await store_fewshot_example(
            tenant_id="t1",
            agent_id="a1",
            user_message="Q",
            ai_response="A",
            rating=1,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_store_json_format(self, mock_redis: AsyncMock) -> None:
        with patch("app.engine.feedback_loop.get_redis", return_value=mock_redis):
            await store_fewshot_example(
                tenant_id="t1",
                agent_id="a1",
                user_message="Hello",
                ai_response="World",
                rating=5,
            )
            call_args = mock_redis.zadd.call_args
            key = call_args[0][0]
            mapping = call_args[0][1]
            assert key == "fewshot:t1:a1"
            # mapping is {json_value: score}
            json_val = list(mapping.keys())[0]
            parsed = json.loads(json_val)
            assert parsed["user_message"] == "Hello"
            assert parsed["ai_response"] == "World"
            assert mapping[json_val] == 5.0

    @pytest.mark.asyncio
    async def test_ttl_set(self, mock_redis: AsyncMock) -> None:
        with patch("app.engine.feedback_loop.get_redis", return_value=mock_redis):
            await store_fewshot_example(
                tenant_id="t1", agent_id="a1",
                user_message="Q", ai_response="A", rating=5,
            )
            mock_redis.expire.assert_called_once_with(
                "fewshot:t1:a1", _FEWSHOT_TTL_SECONDS,
            )

    @pytest.mark.asyncio
    async def test_overflow_cleanup(self, mock_redis: AsyncMock) -> None:
        mock_redis.zcard.return_value = 25
        with patch("app.engine.feedback_loop.get_redis", return_value=mock_redis):
            await store_fewshot_example(
                tenant_id="t1", agent_id="a1",
                user_message="Q", ai_response="A", rating=5,
            )
            mock_redis.zremrangebyrank.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_cleanup_when_under_limit(self, mock_redis: AsyncMock) -> None:
        mock_redis.zcard.return_value=10
        with patch("app.engine.feedback_loop.get_redis", return_value=mock_redis):
            await store_fewshot_example(
                tenant_id="t1", agent_id="a1",
                user_message="Q", ai_response="A", rating=5,
            )
            mock_redis.zremrangebyrank.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_error_returns_false(self) -> None:
        failing_redis = AsyncMock()
        failing_redis.zadd = AsyncMock(side_effect=ConnectionError("conn refused"))
        with patch("app.engine.feedback_loop.get_redis", return_value=failing_redis):
            result = await store_fewshot_example(
                tenant_id="t1", agent_id="a1",
                user_message="Q", ai_response="A", rating=5,
            )
            assert result is False


class TestLoadFewshotExamples:
    """Test loading top-k few-shot examples from Redis."""

    @pytest.mark.asyncio
    async def test_load_examples(self, mock_redis: AsyncMock) -> None:
        mock_redis.zrevrange.return_value = [
            json.dumps({"user_message": "Q1", "ai_response": "A1"}),
            json.dumps({"user_message": "Q2", "ai_response": "A2"}),
        ]
        with patch("app.engine.feedback_loop.get_redis", return_value=mock_redis):
            result = await load_fewshot_examples("t1", "a1", top_k=3)
            assert len(result) == 2
            assert result[0]["user_message"] == "Q1"
            assert result[1]["ai_response"] == "A2"

    @pytest.mark.asyncio
    async def test_load_empty(self, mock_redis: AsyncMock) -> None:
        mock_redis.zrevrange.return_value = []
        with patch("app.engine.feedback_loop.get_redis", return_value=mock_redis):
            result = await load_fewshot_examples("t1", "a1")
            assert result == []

    @pytest.mark.asyncio
    async def test_load_no_agent_id(self, mock_redis: AsyncMock) -> None:
        result = await load_fewshot_examples("t1", None)
        assert result == []
        # Redis should not be called
        mock_redis.zrevrange.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_skips_invalid_json(self, mock_redis: AsyncMock) -> None:
        mock_redis.zrevrange.return_value = [
            json.dumps({"user_message": "Q1", "ai_response": "A1"}),
            "not valid json{{{",
            json.dumps({"user_message": "Q3", "ai_response": "A3"}),
        ]
        with patch("app.engine.feedback_loop.get_redis", return_value=mock_redis):
            result = await load_fewshot_examples("t1", "a1")
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_load_skips_missing_keys(self, mock_redis: AsyncMock) -> None:
        mock_redis.zrevrange.return_value = [
            json.dumps({"user_message": "Q1"}),  # missing ai_response
            json.dumps({"user_message": "Q2", "ai_response": "A2"}),
        ]
        with patch("app.engine.feedback_loop.get_redis", return_value=mock_redis):
            result = await load_fewshot_examples("t1", "a1")
            assert len(result) == 1
            assert result[0]["user_message"] == "Q2"

    @pytest.mark.asyncio
    async def test_load_redis_error_returns_empty(self) -> None:
        failing_redis = AsyncMock()
        failing_redis.zrevrange = AsyncMock(side_effect=ConnectionError("down"))
        with patch("app.engine.feedback_loop.get_redis", return_value=failing_redis):
            result = await load_fewshot_examples("t1", "a1")
            assert result == []

    @pytest.mark.asyncio
    async def test_load_custom_top_k(self, mock_redis: AsyncMock) -> None:
        mock_redis.zrevrange.return_value = []
        with patch("app.engine.feedback_loop.get_redis", return_value=mock_redis):
            await load_fewshot_examples("t1", "a1", top_k=10)
            mock_redis.zrevrange.assert_called_once_with("fewshot:t1:a1", 0, 9)
