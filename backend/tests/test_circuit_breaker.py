"""Tests for app.agents.circuit_breaker."""

import time
from unittest.mock import patch

import pytest

from app.agents.circuit_breaker import CircuitBreaker


class TestCircuitBreaker:
    """Tests for CircuitBreaker state transitions."""

    def test_new_model_is_available(self) -> None:
        cb = CircuitBreaker(max_failures=3, cooldown_seconds=60)
        assert cb.is_available("deepseek:chat") is True

    def test_stays_available_below_threshold(self) -> None:
        cb = CircuitBreaker(max_failures=3, cooldown_seconds=60)
        cb.record_failure("deepseek:chat")
        cb.record_failure("deepseek:chat")
        # 2 failures, threshold is 3
        assert cb.is_available("deepseek:chat") is True

    def test_opens_at_threshold(self) -> None:
        cb = CircuitBreaker(max_failures=3, cooldown_seconds=60)
        cb.record_failure("deepseek:chat")
        cb.record_failure("deepseek:chat")
        cb.record_failure("deepseek:chat")
        # 3 failures = open
        assert cb.is_available("deepseek:chat") is False

    def test_success_resets_failures(self) -> None:
        cb = CircuitBreaker(max_failures=3, cooldown_seconds=60)
        cb.record_failure("deepseek:chat")
        cb.record_failure("deepseek:chat")
        cb.record_success("deepseek:chat")
        # Reset, so 3 more failures needed to open
        cb.record_failure("deepseek:chat")
        cb.record_failure("deepseek:chat")
        assert cb.is_available("deepseek:chat") is True

    def test_success_closes_open_circuit(self) -> None:
        cb = CircuitBreaker(max_failures=2, cooldown_seconds=60)
        cb.record_failure("model-a")
        cb.record_failure("model-a")
        assert cb.is_available("model-a") is False

        cb.record_success("model-a")
        assert cb.is_available("model-a") is True

    def test_half_open_after_cooldown(self) -> None:
        cb = CircuitBreaker(max_failures=2, cooldown_seconds=1)
        cb.record_failure("model-b")
        cb.record_failure("model-b")
        assert cb.is_available("model-b") is False

        # Simulate cooldown by patching time.monotonic
        original_time = time.monotonic()
        with patch("time.monotonic", return_value=original_time + 2):
            assert cb.is_available("model-b") is True

    def test_independent_per_model(self) -> None:
        cb = CircuitBreaker(max_failures=2, cooldown_seconds=60)
        cb.record_failure("model-a")
        cb.record_failure("model-a")
        assert cb.is_available("model-a") is False
        assert cb.is_available("model-b") is True

    def test_many_failures_beyond_threshold(self) -> None:
        cb = CircuitBreaker(max_failures=3, cooldown_seconds=60)
        for _ in range(10):
            cb.record_failure("model-x")
        assert cb.is_available("model-x") is False

    def test_default_parameters(self) -> None:
        cb = CircuitBreaker()
        # Defaults: max_failures=3, cooldown=60
        cb.record_failure("m")
        cb.record_failure("m")
        assert cb.is_available("m") is True
        cb.record_failure("m")
        assert cb.is_available("m") is False
