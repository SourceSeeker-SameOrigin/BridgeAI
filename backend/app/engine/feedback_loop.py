"""Few-shot Learning Loop — 高评分对话自动进入 few-shot 示例池。

当用户对消息评分 >= 4 时，将 user_message + ai_response 存入 Redis ZSET，
后续请求时从 Redis 加载 top-3 示例，注入 prompt_optimizer 的 Layer 3。

Key: fewshot:{tenant_id}:{agent_id}
Score: rating (4 or 5)
Value: JSON {user_message, ai_response}
TTL: 7 days
"""

import json
import logging
from typing import Any, Optional

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

_FEWSHOT_KEY_PREFIX = "fewshot"
_FEWSHOT_TTL_SECONDS = 7 * 24 * 3600  # 7 days
_FEWSHOT_MAX_EXAMPLES = 3
_FEWSHOT_MIN_RATING = 4


def _build_key(tenant_id: str, agent_id: str) -> str:
    return f"{_FEWSHOT_KEY_PREFIX}:{tenant_id}:{agent_id}"


async def store_fewshot_example(
    tenant_id: str,
    agent_id: str,
    user_message: str,
    ai_response: str,
    rating: int,
) -> bool:
    """将高评分对话存入 Redis ZSET 作为 few-shot 示例。

    仅当 rating >= 4 时存储。返回是否成功存储。
    """
    if rating < _FEWSHOT_MIN_RATING:
        return False

    try:
        redis = await get_redis()
        key = _build_key(tenant_id, agent_id)

        value = json.dumps(
            {"user_message": user_message, "ai_response": ai_response},
            ensure_ascii=False,
        )

        # 使用 rating 作为 score，相同内容会自动去重
        await redis.zadd(key, {value: float(rating)})
        # 刷新 TTL
        await redis.expire(key, _FEWSHOT_TTL_SECONDS)

        # 保持 ZSET 不超过 20 条，移除最低评分的
        count = await redis.zcard(key)
        if count > 20:
            await redis.zremrangebyrank(key, 0, count - 21)

        logger.info(
            "Stored few-shot example for tenant=%s agent=%s rating=%d",
            tenant_id, agent_id, rating,
        )
        return True

    except Exception as e:
        logger.warning("Failed to store few-shot example: %s", e)
        return False


async def load_fewshot_examples(
    tenant_id: str,
    agent_id: Optional[str],
    top_k: int = _FEWSHOT_MAX_EXAMPLES,
) -> list[dict[str, str]]:
    """从 Redis 加载 top-k 高评分 few-shot 示例。

    返回格式: [{"user_message": "...", "ai_response": "..."}, ...]
    按评分从高到低排序。
    """
    if not agent_id:
        return []

    try:
        redis = await get_redis()
        key = _build_key(tenant_id, agent_id)

        # 获取评分最高的 top_k 条（倒序）
        results = await redis.zrevrange(key, 0, top_k - 1)

        examples: list[dict[str, str]] = []
        for item in results:
            try:
                data = json.loads(item)
                if "user_message" in data and "ai_response" in data:
                    examples.append(data)
            except (json.JSONDecodeError, TypeError):
                continue

        return examples

    except Exception as e:
        logger.warning("Failed to load few-shot examples: %s", e)
        return []
