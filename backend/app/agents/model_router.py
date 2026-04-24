"""
Model Router — 5-layer routing logic for selecting the optimal model.

Layer 1: Use agent's configured default model for first message.
Layer 2: For subsequent messages, adjust model based on intent/complexity analysis.
Layer 3: User tier adjustment (stub — for future premium tier routing).
Layer 4: Performance optimization — early turns & simple intents use cheapest model.
Layer 5: Cost control — when cost_optimization enabled, downgrade if quality threshold met.
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Model capability tiers: maps provider -> model list ordered by capability (low to high)
MODEL_TIERS: dict[str, list[str]] = {
    "anthropic": [
        "claude-haiku-3-20240307",
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
    ],
    "deepseek": [
        "deepseek-v4-pro",
    ],
    "qwen": [
        "qwen-turbo",
        "qwen-plus",
        "qwen-max",
    ],
}

# Intents that benefit from stronger models
_COMPLEX_INTENTS = {"debugging", "generation", "analysis", "coding"}
_SIMPLE_INTENTS = {"general", "greeting", "question"}

# Intents suitable for the fastest/cheapest model (Layer 4)
_FAST_INTENTS = {"small_talk", "greeting"}

# Early conversation threshold for Layer 4 performance optimization
_EARLY_TURN_THRESHOLD = 3

# Default quality threshold for Layer 5 cost control (complexity <= this → downgrade)
_COST_QUALITY_THRESHOLD = "low"


@dataclass(frozen=True)
class RoutingResult:
    """Immutable routing decision."""

    provider_name: str
    model_id: str
    reason: str


def resolve_provider_model(
    agent_config: dict[str, Any] | None,
    request_model: str | None = None,
) -> tuple[str, str]:
    """
    Extract provider and model from agent config or request.
    Returns (provider_name, model_id).
    """
    config = agent_config or {}

    # Request-level override takes priority
    if request_model:
        # Try to infer provider from model name
        provider = _infer_provider(request_model)
        return provider, request_model

    # From agent's model_config
    provider = config.get("model_provider", config.get("provider", ""))
    model = config.get("model_name", config.get("model", ""))

    if not provider and model:
        provider = _infer_provider(model)
    if not model and provider:
        # Default model for provider
        model = _default_model_for_provider(provider)

    # Fallback: first available
    if not provider or not model:
        provider = "deepseek"
        model = "deepseek-v4-pro"

    return provider, model


def _infer_provider(model_name: str) -> str:
    """Infer provider from model name heuristics."""
    lower = model_name.lower()
    if "claude" in lower or "anthropic" in lower:
        return "anthropic"
    if "deepseek" in lower:
        return "deepseek"
    if "qwen" in lower:
        return "qwen"
    if "gpt" in lower or "o1" in lower or "o3" in lower:
        return "openai"
    return "deepseek"  # default fallback


def _default_model_for_provider(provider: str) -> str:
    """Return a sensible default model for each provider."""
    defaults = {
        "anthropic": "claude-sonnet-4-20250514",
        "deepseek": "deepseek-v4-pro",
        "qwen": "qwen-plus",
    }
    return defaults.get(provider, "deepseek-v4-pro")


def route_model(
    agent_config: dict[str, Any] | None,
    request_model: str | None = None,
    previous_analysis: dict[str, Any] | None = None,
    message_index: int = 0,
    user_tier: str = "free",
    cost_optimization: bool = False,
) -> RoutingResult:
    """
    5-layer model routing.

    Args:
        agent_config: Agent's model_config JSONB dict.
        request_model: Explicit model override from the request.
        previous_analysis: Analysis from the previous assistant message (intent, complexity).
        message_index: How many user messages have been sent in this conversation.
        user_tier: User subscription tier (free, pro, enterprise). Stub for now.
        cost_optimization: Whether to enable Layer 5 cost-control downgrade.

    Returns:
        RoutingResult with provider_name, model_id, and reason.
    """
    provider, model = resolve_provider_model(agent_config, request_model)

    # --- Layer 1: Default model (first message or no analysis) ---
    if message_index == 0 or previous_analysis is None:
        return RoutingResult(
            provider_name=provider,
            model_id=model,
            reason="layer1:default_model",
        )

    # --- Layer 2: Adjust based on previous analysis ---
    intent = previous_analysis.get("intent", "general")
    confidence = previous_analysis.get("confidence", 0.5)
    complexity = previous_analysis.get("complexity", "medium")

    tiers = MODEL_TIERS.get(provider, [])
    if not tiers:
        return RoutingResult(
            provider_name=provider,
            model_id=model,
            reason="layer2:no_tier_info",
        )

    current_tier_idx = _find_tier_index(tiers, model)
    selected_model = model
    reason = "layer2:no_change"

    if intent in _COMPLEX_INTENTS and confidence > 0.7:
        # Upgrade to a stronger model if possible
        new_idx = min(current_tier_idx + 1, len(tiers) - 1)
        selected_model = tiers[new_idx]
        if selected_model != model:
            current_tier_idx = new_idx
            reason = f"layer2:upgrade_for_{intent}"

    elif intent in _SIMPLE_INTENTS and confidence > 0.8:
        # Downgrade to save cost
        new_idx = max(current_tier_idx - 1, 0)
        selected_model = tiers[new_idx]
        if selected_model != model:
            current_tier_idx = new_idx
            reason = f"layer2:downgrade_for_{intent}"

    # --- Layer 3: User tier adjustment (stub) ---
    # In the future, premium users could force higher-tier models.

    # --- Layer 4: Performance optimization ---
    # For early conversation turns (< 3 messages) with simple/fast intents,
    # use the fastest (cheapest) model to reduce latency.
    if message_index < _EARLY_TURN_THRESHOLD and intent in _FAST_INTENTS:
        fastest_model = tiers[0]
        if fastest_model != selected_model:
            logger.info(
                "Layer4: early turn %d + fast intent '%s' → downgrade %s → %s",
                message_index, intent, selected_model, fastest_model,
            )
            selected_model = fastest_model
            current_tier_idx = 0
            reason = f"layer4:fast_intent_{intent}"

    # --- Layer 5: Cost control ---
    # When cost_optimization is enabled in config, downgrade to cheaper model
    # if the conversation complexity is low enough (quality threshold met).
    if cost_optimization and complexity in ("low", _COST_QUALITY_THRESHOLD):
        cheapest_idx = max(current_tier_idx - 1, 0)
        cheaper_model = tiers[cheapest_idx]
        if cheaper_model != selected_model:
            logger.info(
                "Layer5: cost_optimization + complexity='%s' → downgrade %s → %s",
                complexity, selected_model, cheaper_model,
            )
            selected_model = cheaper_model
            reason = f"layer5:cost_downgrade_complexity_{complexity}"

    return RoutingResult(
        provider_name=provider,
        model_id=selected_model,
        reason=reason,
    )


def _find_tier_index(tiers: list[str], model: str) -> int:
    """Find the tier index for a model, defaulting to middle if not found."""
    try:
        return tiers.index(model)
    except ValueError:
        return len(tiers) // 2
