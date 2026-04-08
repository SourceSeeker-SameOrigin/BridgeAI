"""Provider registry — auto-discovers configured providers from environment."""

import logging
from typing import Any

from app.config import settings
from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Default proxy for overseas APIs (from user's CLAUDE.md)
_OVERSEAS_PROXY = "http://127.0.0.1:1087"


class ProviderRegistry:
    """
    Singleton registry that manages LLM provider instances.
    Auto-discovers providers from env (API keys in settings).
    """

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._auto_discover()

    def _auto_discover(self) -> None:
        """Discover and register providers based on available API keys."""
        # Anthropic (overseas, needs proxy)
        if settings.ANTHROPIC_API_KEY:
            try:
                from app.providers.anthropic_provider import AnthropicProvider

                provider = AnthropicProvider(
                    api_key=settings.ANTHROPIC_API_KEY,
                    proxy_url=_OVERSEAS_PROXY,
                )
                self._providers["anthropic"] = provider
                logger.info("Registered provider: anthropic")
            except Exception as e:
                logger.warning("Failed to register anthropic provider: %s", e)

        # DeepSeek (overseas API, relies on system HTTP_PROXY/HTTPS_PROXY)
        if settings.DEEPSEEK_API_KEY:
            try:
                from app.providers.deepseek_provider import DeepSeekProvider

                provider = DeepSeekProvider(api_key=settings.DEEPSEEK_API_KEY)
                self._providers["deepseek"] = provider
                logger.info("Registered provider: deepseek")
            except Exception as e:
                logger.warning("Failed to register deepseek provider: %s", e)

        # Qwen (China-based, no proxy)
        if settings.QWEN_API_KEY:
            try:
                from app.providers.qwen_provider import QwenProvider

                provider = QwenProvider(api_key=settings.QWEN_API_KEY)
                self._providers["qwen"] = provider
                logger.info("Registered provider: qwen")
            except Exception as e:
                logger.warning("Failed to register qwen provider: %s", e)

        # Ollama (local models, no auth, no proxy)
        if settings.OLLAMA_BASE_URL:
            try:
                from app.providers.ollama_provider import OllamaProvider

                provider = OllamaProvider(base_url=settings.OLLAMA_BASE_URL)
                self._providers["ollama"] = provider
                logger.info("Registered provider: ollama")
            except Exception as e:
                logger.warning("Failed to register ollama provider: %s", e)

        if not self._providers:
            logger.warning(
                "No LLM providers configured. "
                "Set ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, QWEN_API_KEY, or OLLAMA_BASE_URL in .env"
            )

    def register(self, name: str, provider: LLMProvider) -> None:
        """Manually register a provider."""
        self._providers[name] = provider
        logger.info("Manually registered provider: %s", name)

    def get_provider(self, provider_name: str) -> LLMProvider:
        """
        Get a provider by name.

        Raises:
            ValueError: If provider is not found/configured.
        """
        self._ensure_initialized()
        provider = self._providers.get(provider_name)
        if provider is None:
            available = list(self._providers.keys())
            raise ValueError(
                f"Provider '{provider_name}' not configured. "
                f"Available providers: {available}. "
                f"Check your API key settings in .env"
            )
        return provider

    def get_any_provider(self) -> tuple[str, LLMProvider]:
        """
        Get any available provider (first one found).

        Returns:
            Tuple of (provider_name, provider).

        Raises:
            ValueError: If no providers are configured.
        """
        self._ensure_initialized()
        if not self._providers:
            raise ValueError(
                "No LLM providers configured. "
                "Set at least one API key in .env (ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, QWEN_API_KEY)"
            )
        name = next(iter(self._providers))
        return name, self._providers[name]

    def list_providers(self) -> list[str]:
        """List names of all registered providers."""
        self._ensure_initialized()
        return list(self._providers.keys())

    async def close_all(self) -> None:
        """Close all provider HTTP clients."""
        for name, provider in self._providers.items():
            try:
                await provider.close()
            except Exception as e:
                logger.warning("Error closing provider %s: %s", name, e)
        self._providers.clear()
        self._initialized = False


# Module-level singleton
_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry singleton."""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
