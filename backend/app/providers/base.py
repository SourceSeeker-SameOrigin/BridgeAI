"""Abstract base class for LLM provider adapters."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResponse:
    """Immutable response from an LLM call."""

    content: str
    model: str
    finish_reason: str = "stop"
    token_input: int = 0
    token_output: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class StreamChunk:
    """A single chunk in a streaming response."""

    type: str  # "content", "tool_call", "done"
    content: str = ""
    tool_name: str = ""
    tool_arguments: dict[str, Any] = field(default_factory=dict)
    # Usage info only available in the final chunk
    token_input: int = 0
    token_output: int = 0
    finish_reason: str | None = None


class LLMProvider(ABC):
    """Abstract base class for all LLM provider adapters."""

    provider_name: str = "base"

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        *,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse | AsyncGenerator[StreamChunk, None]:
        """
        Send a chat request to the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model: Model identifier string.
            stream: If True, returns an AsyncGenerator of StreamChunks.
            tools: Optional tool definitions for function calling.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.

        Returns:
            LLMResponse for non-streaming, AsyncGenerator[StreamChunk] for streaming.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is reachable and configured."""
        ...

    async def close(self) -> None:
        """Clean up resources (e.g., close HTTP client)."""
        pass
