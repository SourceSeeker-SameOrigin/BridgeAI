"""Tests for app.agents.model_router — 5-layer routing logic."""

import pytest

from app.agents.model_router import (
    MODEL_TIERS,
    RoutingResult,
    _default_model_for_provider,
    _find_tier_index,
    _infer_provider,
    resolve_provider_model,
    route_model,
)


# ---------------------------------------------------------------------------
# resolve_provider_model
# ---------------------------------------------------------------------------

class TestResolveProviderModel:
    """Layer 0: provider/model resolution from config or request."""

    def test_request_model_override(self) -> None:
        provider, model = resolve_provider_model(
            {"model_provider": "qwen", "model_name": "qwen-plus"},
            request_model="claude-sonnet-4-20250514",
        )
        assert model == "claude-sonnet-4-20250514"
        assert provider == "anthropic"

    def test_agent_config_provider_and_model(self) -> None:
        provider, model = resolve_provider_model(
            {"model_provider": "deepseek", "model_name": "deepseek-reasoner"},
        )
        assert provider == "deepseek"
        assert model == "deepseek-reasoner"

    def test_infer_provider_from_model_name(self) -> None:
        provider, model = resolve_provider_model({"model_name": "qwen-max"})
        assert provider == "qwen"
        assert model == "qwen-max"

    def test_default_model_for_provider(self) -> None:
        provider, model = resolve_provider_model({"model_provider": "anthropic"})
        assert provider == "anthropic"
        assert model == "claude-sonnet-4-20250514"

    def test_fallback_when_empty_config(self) -> None:
        provider, model = resolve_provider_model(None)
        assert provider == "deepseek"
        assert model == "deepseek-chat"

    def test_fallback_when_no_provider_no_model(self) -> None:
        provider, model = resolve_provider_model({})
        assert provider == "deepseek"
        assert model == "deepseek-chat"

    def test_legacy_keys(self) -> None:
        provider, model = resolve_provider_model(
            {"provider": "qwen", "model": "qwen-turbo"},
        )
        assert provider == "qwen"
        assert model == "qwen-turbo"


# ---------------------------------------------------------------------------
# _infer_provider
# ---------------------------------------------------------------------------

class TestInferProvider:
    @pytest.mark.parametrize(
        "model_name,expected",
        [
            ("claude-sonnet-4-20250514", "anthropic"),
            ("deepseek-chat", "deepseek"),
            ("qwen-plus", "qwen"),
            ("gpt-4o", "openai"),
            ("o1-preview", "openai"),
            ("o3-mini", "openai"),
            ("unknown-model", "deepseek"),
        ],
    )
    def test_infer_provider(self, model_name: str, expected: str) -> None:
        assert _infer_provider(model_name) == expected


# ---------------------------------------------------------------------------
# Layer 1: Default model (first message)
# ---------------------------------------------------------------------------

class TestLayer1DefaultModel:
    """First message or no analysis → use default model."""

    def test_first_message_returns_default(self) -> None:
        result = route_model(
            agent_config={"model_provider": "anthropic", "model_name": "claude-sonnet-4-20250514"},
            message_index=0,
        )
        assert result.model_id == "claude-sonnet-4-20250514"
        assert result.reason == "layer1:default_model"

    def test_no_analysis_returns_default(self) -> None:
        result = route_model(
            agent_config={"model_provider": "deepseek", "model_name": "deepseek-chat"},
            message_index=5,
            previous_analysis=None,
        )
        assert result.reason == "layer1:default_model"

    def test_first_message_with_request_model_override(self) -> None:
        result = route_model(
            agent_config=None,
            request_model="qwen-max",
            message_index=0,
        )
        assert result.model_id == "qwen-max"
        assert result.provider_name == "qwen"


# ---------------------------------------------------------------------------
# Layer 2: Intent-based adjustment
# ---------------------------------------------------------------------------

class TestLayer2IntentAdjustment:
    """Complex intent → upgrade, simple intent → downgrade."""

    def test_complex_intent_upgrades_model(self) -> None:
        result = route_model(
            agent_config={"model_provider": "anthropic", "model_name": "claude-sonnet-4-20250514"},
            message_index=5,
            previous_analysis={"intent": "analysis", "confidence": 0.9, "complexity": "high"},
        )
        assert result.model_id == "claude-opus-4-20250514"
        assert "upgrade" in result.reason

    def test_simple_intent_downgrades_model(self) -> None:
        result = route_model(
            agent_config={"model_provider": "anthropic", "model_name": "claude-sonnet-4-20250514"},
            message_index=5,
            previous_analysis={"intent": "general", "confidence": 0.9, "complexity": "low"},
        )
        assert result.model_id == "claude-haiku-3-20240307"
        assert "downgrade" in result.reason

    def test_low_confidence_no_change(self) -> None:
        result = route_model(
            agent_config={"model_provider": "anthropic", "model_name": "claude-sonnet-4-20250514"},
            message_index=5,
            previous_analysis={"intent": "analysis", "confidence": 0.3, "complexity": "medium"},
        )
        assert result.model_id == "claude-sonnet-4-20250514"
        assert result.reason == "layer2:no_change"

    def test_already_highest_tier_stays(self) -> None:
        result = route_model(
            agent_config={"model_provider": "anthropic", "model_name": "claude-opus-4-20250514"},
            message_index=5,
            previous_analysis={"intent": "coding", "confidence": 0.95, "complexity": "high"},
        )
        # Already at highest tier, can't upgrade further
        assert result.model_id == "claude-opus-4-20250514"

    def test_already_lowest_tier_stays(self) -> None:
        result = route_model(
            agent_config={"model_provider": "anthropic", "model_name": "claude-haiku-3-20240307"},
            message_index=5,
            previous_analysis={"intent": "greeting", "confidence": 0.95, "complexity": "low"},
        )
        assert result.model_id == "claude-haiku-3-20240307"

    def test_deepseek_intent_upgrade(self) -> None:
        result = route_model(
            agent_config={"model_provider": "deepseek", "model_name": "deepseek-chat"},
            message_index=5,
            previous_analysis={"intent": "debugging", "confidence": 0.85, "complexity": "high"},
        )
        assert result.model_id == "deepseek-reasoner"
        assert "upgrade" in result.reason

    def test_qwen_intent_downgrade(self) -> None:
        result = route_model(
            agent_config={"model_provider": "qwen", "model_name": "qwen-plus"},
            message_index=5,
            previous_analysis={"intent": "question", "confidence": 0.85, "complexity": "low"},
        )
        assert result.model_id == "qwen-turbo"
        assert "downgrade" in result.reason


# ---------------------------------------------------------------------------
# Layer 3: Complexity adjustment (currently a stub — just verify no crash)
# ---------------------------------------------------------------------------

class TestLayer3UserTier:
    def test_free_tier_does_not_crash(self) -> None:
        result = route_model(
            agent_config={"model_provider": "deepseek", "model_name": "deepseek-chat"},
            message_index=2,
            previous_analysis={"intent": "general", "confidence": 0.5},
            user_tier="free",
        )
        assert isinstance(result, RoutingResult)

    def test_enterprise_tier_does_not_crash(self) -> None:
        result = route_model(
            agent_config={"model_provider": "deepseek", "model_name": "deepseek-chat"},
            message_index=2,
            previous_analysis={"intent": "general", "confidence": 0.5},
            user_tier="enterprise",
        )
        assert isinstance(result, RoutingResult)


# ---------------------------------------------------------------------------
# Layer 4: Performance optimization (early turns + fast intent)
# ---------------------------------------------------------------------------

class TestLayer4PerformanceOptimization:
    """Early conversation turns with fast/simple intents → cheapest model."""

    def test_early_turn_small_talk_uses_cheapest(self) -> None:
        result = route_model(
            agent_config={"model_provider": "anthropic", "model_name": "claude-sonnet-4-20250514"},
            message_index=1,
            previous_analysis={"intent": "small_talk", "confidence": 0.9, "complexity": "low"},
        )
        assert result.model_id == "claude-haiku-3-20240307"
        assert "layer4" in result.reason

    def test_early_turn_greeting_uses_cheapest(self) -> None:
        result = route_model(
            agent_config={"model_provider": "qwen", "model_name": "qwen-max"},
            message_index=2,
            previous_analysis={"intent": "greeting", "confidence": 0.9, "complexity": "low"},
        )
        assert result.model_id == "qwen-turbo"
        assert "layer4" in result.reason

    def test_late_turn_small_talk_no_layer4(self) -> None:
        # message_index >= 3 → layer4 doesn't apply
        result = route_model(
            agent_config={"model_provider": "anthropic", "model_name": "claude-sonnet-4-20250514"},
            message_index=5,
            previous_analysis={"intent": "small_talk", "confidence": 0.9, "complexity": "low"},
        )
        # small_talk is in _SIMPLE_INTENTS? No, it's not in _SIMPLE_INTENTS,
        # but _FAST_INTENTS. Layer4 won't trigger at index>=3.
        assert "layer4" not in result.reason

    def test_early_turn_complex_intent_no_layer4(self) -> None:
        result = route_model(
            agent_config={"model_provider": "anthropic", "model_name": "claude-sonnet-4-20250514"},
            message_index=1,
            previous_analysis={"intent": "debugging", "confidence": 0.9, "complexity": "high"},
        )
        # debugging is not a fast intent
        assert "layer4" not in result.reason


# ---------------------------------------------------------------------------
# Layer 5: Cost control
# ---------------------------------------------------------------------------

class TestLayer5CostControl:
    """cost_optimization + low complexity → downgrade."""

    def test_cost_optimization_downgrades_on_low_complexity(self) -> None:
        result = route_model(
            agent_config={"model_provider": "anthropic", "model_name": "claude-sonnet-4-20250514"},
            message_index=5,
            previous_analysis={"intent": "general", "confidence": 0.5, "complexity": "low"},
            cost_optimization=True,
        )
        assert result.model_id == "claude-haiku-3-20240307"
        assert "layer5" in result.reason

    def test_cost_optimization_disabled_no_downgrade(self) -> None:
        result = route_model(
            agent_config={"model_provider": "anthropic", "model_name": "claude-sonnet-4-20250514"},
            message_index=5,
            previous_analysis={"intent": "general", "confidence": 0.5, "complexity": "low"},
            cost_optimization=False,
        )
        # Without cost_optimization, layer5 won't trigger
        assert "layer5" not in result.reason

    def test_cost_optimization_high_complexity_no_downgrade(self) -> None:
        result = route_model(
            agent_config={"model_provider": "anthropic", "model_name": "claude-sonnet-4-20250514"},
            message_index=5,
            previous_analysis={"intent": "general", "confidence": 0.5, "complexity": "high"},
            cost_optimization=True,
        )
        assert "layer5" not in result.reason


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestFindTierIndex:
    def test_known_model(self) -> None:
        tiers = MODEL_TIERS["anthropic"]
        assert _find_tier_index(tiers, "claude-sonnet-4-20250514") == 1

    def test_unknown_model_falls_to_middle(self) -> None:
        tiers = MODEL_TIERS["anthropic"]
        idx = _find_tier_index(tiers, "unknown-model")
        assert idx == len(tiers) // 2


class TestDefaultModelForProvider:
    @pytest.mark.parametrize(
        "provider,expected",
        [
            ("anthropic", "claude-sonnet-4-20250514"),
            ("deepseek", "deepseek-chat"),
            ("qwen", "qwen-plus"),
            ("unknown", "deepseek-chat"),
        ],
    )
    def test_defaults(self, provider: str, expected: str) -> None:
        assert _default_model_for_provider(provider) == expected


class TestNoTierInfo:
    """Provider with no tier info in MODEL_TIERS."""

    def test_unknown_provider_returns_layer2_no_tier_info(self) -> None:
        result = route_model(
            agent_config={"model_provider": "openai", "model_name": "gpt-4o"},
            message_index=5,
            previous_analysis={"intent": "analysis", "confidence": 0.9, "complexity": "high"},
        )
        assert result.reason == "layer2:no_tier_info"
        assert result.model_id == "gpt-4o"
