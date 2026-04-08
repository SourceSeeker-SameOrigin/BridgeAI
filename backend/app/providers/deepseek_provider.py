"""DeepSeek provider — thin wrapper over OpenAI-compatible provider."""

import logging

from app.providers.openai_compat_provider import OpenAICompatProvider

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


class DeepSeekProvider(OpenAICompatProvider):
    """
    DeepSeek uses the OpenAI-compatible chat/completions API.
    Default base_url: https://api.deepseek.com/v1
    Overseas API — relies on system HTTP_PROXY/HTTPS_PROXY env vars.
    """

    provider_name = "deepseek"

    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url or DEEPSEEK_BASE_URL,
            provider_name="deepseek",
            proxy_url=None,  # httpx picks up system HTTP_PROXY/HTTPS_PROXY automatically
        )
