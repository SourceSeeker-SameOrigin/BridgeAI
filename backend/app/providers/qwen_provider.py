"""Qwen provider — thin wrapper over OpenAI-compatible provider.

Qwen (通义千问) uses DashScope's OpenAI-compatible API.
China-based API — must NOT use proxy.
"""

import logging

from app.providers.openai_compat_provider import OpenAICompatProvider

logger = logging.getLogger(__name__)

QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class QwenProvider(OpenAICompatProvider):
    """
    Qwen provider via DashScope OpenAI-compatible API.
    Supported models: qwen-max, qwen-plus, qwen-turbo, etc.
    China-based API — explicitly disables proxy.
    """

    provider_name = "qwen"

    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url or QWEN_BASE_URL,
            provider_name="qwen",
            proxy_url=None,  # China API, no proxy
        )
