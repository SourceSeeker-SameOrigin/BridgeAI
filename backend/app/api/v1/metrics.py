"""Prometheus metrics endpoint.

Uses prometheus-fastapi-instrumentator for automatic HTTP metrics collection,
plus custom BridgeAI-specific gauges and counters.
"""

from prometheus_client import Counter, Gauge

# -- Custom BridgeAI metrics --

# LLM usage
llm_requests_total = Counter(
    "bridgeai_llm_requests_total",
    "Total LLM API requests",
    ["provider", "model"],
)

llm_tokens_total = Counter(
    "bridgeai_llm_tokens_total",
    "Total tokens used by LLM calls",
    ["type"],  # "prompt" or "completion"
)

# Conversations
active_conversations = Gauge(
    "bridgeai_active_conversations",
    "Number of active conversations (updated periodically)",
)

# Circuit breaker
circuit_breaker_state = Gauge(
    "bridgeai_circuit_breaker_open",
    "Whether the circuit breaker is open for a model (1=open, 0=closed)",
    ["model_key"],
)
