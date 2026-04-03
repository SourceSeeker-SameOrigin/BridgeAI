"""
Circuit Breaker for LLM calls.

Tracks failure counts per model. After N consecutive failures, opens the circuit
for a cooldown period. Provides a fallback chain to try alternative models.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from app.providers.base import LLMProvider, LLMResponse, StreamChunk

logger = logging.getLogger(__name__)

# Defaults
_MAX_FAILURES = 3
_COOLDOWN_SECONDS = 60.0


@dataclass
class _CircuitState:
    """Mutable state for a single model's circuit."""

    failure_count: int = 0
    last_failure_time: float = 0.0
    is_open: bool = False


class CircuitBreaker:
    """
    Circuit breaker with per-model tracking and fallback chain.

    States:
    - CLOSED: normal operation, requests pass through.
    - OPEN: after max_failures consecutive failures, block requests for cooldown_seconds.
    - HALF-OPEN: after cooldown, allow one request to test recovery.
    """

    def __init__(
        self,
        max_failures: int = _MAX_FAILURES,
        cooldown_seconds: float = _COOLDOWN_SECONDS,
    ) -> None:
        self._max_failures = max_failures
        self._cooldown_seconds = cooldown_seconds
        self._states: dict[str, _CircuitState] = {}

    def _get_state(self, model_key: str) -> _CircuitState:
        if model_key not in self._states:
            self._states[model_key] = _CircuitState()
        return self._states[model_key]

    def is_available(self, model_key: str) -> bool:
        """Check if a model is available (circuit not open)."""
        state = self._get_state(model_key)
        if not state.is_open:
            return True
        # Check if cooldown has elapsed (half-open)
        elapsed = time.monotonic() - state.last_failure_time
        if elapsed >= self._cooldown_seconds:
            logger.info("Circuit half-open for %s (cooldown elapsed)", model_key)
            return True
        return False

    def record_success(self, model_key: str) -> None:
        """Record a successful call, resetting the circuit."""
        state = self._get_state(model_key)
        if state.failure_count > 0 or state.is_open:
            logger.info("Circuit closed for %s (success after failures)", model_key)
        state.failure_count = 0
        state.is_open = False

    def record_failure(self, model_key: str) -> None:
        """Record a failed call. Opens circuit after max_failures."""
        state = self._get_state(model_key)
        state.failure_count += 1
        state.last_failure_time = time.monotonic()

        if state.failure_count >= self._max_failures:
            state.is_open = True
            logger.warning(
                "Circuit OPEN for %s (%d consecutive failures, cooldown %.0fs)",
                model_key, state.failure_count, self._cooldown_seconds,
            )

    async def call_with_fallback(
        self,
        provider_getter: "callable",
        messages: list[dict[str, Any]],
        primary_provider: str,
        primary_model: str,
        fallback_chain: list[tuple[str, str]],
        *,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> tuple[str, str, LLMResponse | AsyncGenerator[StreamChunk, None]]:
        """
        Call the primary model, falling back through the chain if the circuit is open or call fails.

        Args:
            provider_getter: Callable(provider_name) -> LLMProvider.
            messages: Chat messages.
            primary_provider: Primary provider name.
            primary_model: Primary model ID.
            fallback_chain: List of (provider_name, model_id) fallbacks.
            stream: Whether to stream.
            tools: Tool definitions.
            temperature: Sampling temperature.
            max_tokens: Max tokens.

        Returns:
            Tuple of (used_provider, used_model, response).

        Raises:
            RuntimeError: If all models in the chain fail.
        """
        candidates = [(primary_provider, primary_model)] + list(fallback_chain)
        last_error: Exception | None = None

        for provider_name, model_id in candidates:
            model_key = f"{provider_name}:{model_id}"

            if not self.is_available(model_key):
                logger.info("Skipping %s (circuit open)", model_key)
                continue

            try:
                provider = provider_getter(provider_name)
            except ValueError as e:
                logger.warning("Provider not available: %s", e)
                continue

            try:
                result = await provider.chat(
                    messages=messages,
                    model=model_id,
                    stream=stream,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                self.record_success(model_key)
                return provider_name, model_id, result

            except Exception as e:
                self.record_failure(model_key)
                last_error = e
                logger.warning(
                    "LLM call failed for %s: %s. Trying fallback...",
                    model_key, str(e)[:200],
                )

        error_msg = f"All models failed. Last error: {last_error}" if last_error else "No available models"
        raise RuntimeError(error_msg)


# Module-level singleton
_circuit_breaker: CircuitBreaker | None = None


def get_circuit_breaker() -> CircuitBreaker:
    """Get the global circuit breaker singleton."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker
