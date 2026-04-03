"""
LangGraph 6-Stage Agent Pipeline.

Architecture:
  Stage 1: Intent Understanding (意图理解)
    — Keyword-based pre-classification before LLM call.
    — Informs model routing and prompt hints.

  Stage 2: Context Enrichment (上下文增强)
    — Loads history, injects RAG context, builds 4-layer optimized prompt.
    — Integrates prompt_optimizer for system/agent/context/analysis fusion.

  Stage 3: Tool Selection (工具选择)
    — Validates MCP tool definitions for the agent.
    — Filters tools with missing required fields.

  Stage 4: Execution Routing (执行路由)
    — 5-layer model routing: default → intent-based → user-tier → performance → cost.
    — Selects provider, model, temperature, max_tokens.

  For *streaming*, stages 1-4 run inside the LangGraph preparation graph.
  The caller then drives real token-by-token streaming (Stage 5) and calls
  post-processing helpers (Stage 6).

  Stage 5: Execution (执行)
    — LLM call via circuit breaker with fallback chain.
    — Tool-call loop: up to 5 rounds of tool execution + re-query.
    — Handled by chat_service (outside graph for streaming support).

  Stage 6: Result Integration & Output (结果整合 + 输出生成)
    — Parse <analysis> JSON block (intent, emotion, confidence, topics).
    — Strip analysis from user-visible content.
    — Persist message with structured intent/emotion metadata.
    — Handled by chat_service via post_process_response().
"""

import logging
import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.model_router import route_model
from app.engine.context_parser import parse_analysis, strip_analysis
from app.engine.prompt_optimizer import build_optimized_prompt

logger = logging.getLogger(__name__)

# Simple keyword-based intent pre-classifier (runs before LLM for routing hints)
_INTENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("debugging", re.compile(
        r"(报错|错误|error|bug|exception|traceback|fix|修复|调试|debug|stack\s?trace|异常)",
        re.IGNORECASE,
    )),
    ("generation", re.compile(
        r"(生成|创建|写一个|write|create|generate|implement|实现|编写|帮我写)",
        re.IGNORECASE,
    )),
    ("summarization", re.compile(
        r"(总结|概括|摘要|summarize|summary|概述|归纳|tl;?dr)",
        re.IGNORECASE,
    )),
    ("question", re.compile(
        r"(什么|为什么|怎么|如何|是否|what|why|how|when|where|who|which|can|could|is|are|do|does|吗|呢)",
        re.IGNORECASE,
    )),
    ("small_talk", re.compile(
        r"^(hi|hello|hey|你好|嗨|哈喽|早上好|晚上好|下午好|good\s*(morning|afternoon|evening)|thanks|谢谢|再见|bye)[\s!！。.？?]*$",
        re.IGNORECASE,
    )),
    ("greeting", re.compile(
        r"^(hi|hello|hey|你好|嗨|哈喽)[\s!！。.]*$",
        re.IGNORECASE,
    )),
]


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------

class PipelineState(TypedDict, total=False):
    """Typed state flowing through the LangGraph pipeline."""

    # --- Input (set by caller before graph invocation) ---
    user_message: str
    history_messages: list[dict[str, str]]  # DB history [{role, content}]
    agent_system_prompt: str | None
    agent_config: dict[str, Any]  # agent.model_config_ or {}
    agent_tools: list[str]  # agent.tools JSON list (connector IDs)
    knowledge_base_id: str | None
    request_model: str | None
    request_temperature: float | None
    request_max_tokens: int | None
    previous_analysis: dict[str, Any] | None
    message_index: int  # how many messages in conversation so far
    fewshot_examples: list[dict[str, str]]  # few-shot examples from feedback loop

    # --- Stage 1: Intent Understanding ---
    intent: str | None
    intent_confidence: float

    # --- Stage 2: Context Enrichment ---
    rag_context: str | None
    optimized_messages: list[dict[str, Any]]

    # --- Stage 3: Tool Selection ---
    available_tools: list[dict[str, Any]]  # OpenAI-format tool defs
    mcp_connector_ids: list[str]  # connector IDs with active tools

    # --- Stage 4: Execution Routing ---
    provider_name: str
    model_id: str
    temperature: float
    max_tokens: int
    routing_reason: str

    # --- Error ---
    error: str | None


# ---------------------------------------------------------------------------
# Stage 1: Intent Understanding (意图理解)
# ---------------------------------------------------------------------------

def understand_intent(state: PipelineState) -> dict[str, Any]:
    """Fast keyword-based intent pre-classification.

    This runs *before* the LLM call to inform model routing and prompt hints.
    The LLM will produce a more accurate classification in <analysis>.
    """
    user_msg = state.get("user_message", "")
    previous = state.get("previous_analysis")

    # If we have a previous analysis with high confidence, bias toward it
    if previous and isinstance(previous, dict) and previous.get("confidence", 0) > 0.8:
        return {
            "intent": previous.get("intent", "general"),
            "intent_confidence": previous.get("confidence", 0.8),
        }

    # Keyword matching
    for intent_name, pattern in _INTENT_PATTERNS:
        if pattern.search(user_msg):
            return {"intent": intent_name, "intent_confidence": 0.6}

    return {"intent": "general", "intent_confidence": 0.3}


# ---------------------------------------------------------------------------
# Stage 2: Context Enrichment (上下文增强)
# ---------------------------------------------------------------------------

def enrich_context(state: PipelineState) -> dict[str, Any]:
    """Build optimized messages from history + RAG context + prompt fusion.

    Integrates prompt_optimizer's 4-layer fusion:
      Layer 1: Base BridgeAI system behavior
      Layer 2: Agent-specific system prompt
      Layer 3: Intent-aware context hints
      Layer 4: Structured analysis instruction
    """
    history = state.get("history_messages", [])
    user_msg = state.get("user_message", "")
    system_prompt = state.get("agent_system_prompt")
    intent = state.get("intent")
    rag_context = state.get("rag_context")

    fewshot_examples = state.get("fewshot_examples", [])

    # If RAG context was injected (by caller before graph), prepend to system prompt
    enriched_system = system_prompt or ""
    if rag_context:
        rag_section = (
            "\n\n## 参考资料（来自知识库检索）\n"
            f"{rag_context}\n\n"
            "请结合以上参考资料回答用户问题，如参考资料不相关则忽略。"
        )
        enriched_system = f"{enriched_system}{rag_section}" if enriched_system else rag_section

    # Append current user message to history
    all_messages = list(history) + [{"role": "user", "content": user_msg}]

    optimized = build_optimized_prompt(
        system_prompt=enriched_system or None,
        messages=all_messages,
        intent=intent,
        fewshot_examples=fewshot_examples,
    )

    return {"optimized_messages": optimized}


# ---------------------------------------------------------------------------
# Stage 3: Tool Selection (工具选择)
# ---------------------------------------------------------------------------

def select_tools(state: PipelineState) -> dict[str, Any]:
    """Resolve which MCP tools are available for this agent.

    Actual tool listing requires async I/O (MCP gateway), so the caller
    pre-populates ``available_tools`` and ``mcp_connector_ids`` before
    invoking the graph. This node validates and filters.
    """
    tools = state.get("available_tools", [])
    connector_ids = state.get("mcp_connector_ids", [])

    # Filter out tools with missing required fields
    valid_tools: list[dict[str, Any]] = []
    for tool in tools:
        if tool.get("type") == "function" and tool.get("function", {}).get("name"):
            valid_tools.append(tool)

    return {
        "available_tools": valid_tools,
        "mcp_connector_ids": connector_ids,
    }


# ---------------------------------------------------------------------------
# Stage 4: Execution Routing (执行路由)
# ---------------------------------------------------------------------------

def route_model_node(state: PipelineState) -> dict[str, Any]:
    """Select provider and model based on agent config, intent, and history.

    Uses 5-layer routing from model_router:
      Layer 1: Default agent model (first message)
      Layer 2: Adjust based on intent/complexity from previous analysis
      Layer 3: User tier adjustment (stub for future)
      Layer 4: Performance optimization for early turns & simple intents
      Layer 5: Cost control downgrade when cost_optimization enabled
    """
    agent_config = state.get("agent_config", {})
    request_model = state.get("request_model")
    previous_analysis = state.get("previous_analysis")
    message_index = state.get("message_index", 0)
    cost_optimization = agent_config.get("cost_optimization", False)

    routing = route_model(
        agent_config=agent_config,
        request_model=request_model,
        previous_analysis=previous_analysis,
        message_index=message_index,
        cost_optimization=cost_optimization,
    )

    temperature = state.get("request_temperature") or agent_config.get("temperature", 0.7)
    max_tokens = state.get("request_max_tokens") or agent_config.get("max_tokens", 4096)

    return {
        "provider_name": routing.provider_name,
        "model_id": routing.model_id,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "routing_reason": routing.reason,
    }


# ---------------------------------------------------------------------------
# Post-Processing Helpers (Stage 5-6, called by chat_service)
# ---------------------------------------------------------------------------

def post_process_response(full_content: str) -> tuple[dict[str, Any] | None, str]:
    """Stage 6: Parse <analysis> block and strip it from user-visible content.

    Args:
        full_content: Raw LLM response including potential <analysis> block.

    Returns:
        Tuple of (analysis_dict_or_none, clean_content_for_user).
    """
    analysis = parse_analysis(full_content)
    clean_content = strip_analysis(full_content)
    return analysis, clean_content


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------

def build_preparation_graph() -> Any:
    """Build the LangGraph for stages 1-4 (preparation before LLM call).

    This graph is used by both streaming and non-streaming paths.
    It takes input state and produces routing + optimized messages.

    Flow:
      understand_intent → enrich_context → select_tools → route_model → END

    Returns a compiled LangGraph runnable.
    """
    graph = StateGraph(PipelineState)

    graph.add_node("understand_intent", understand_intent)
    graph.add_node("enrich_context", enrich_context)
    graph.add_node("select_tools", select_tools)
    graph.add_node("route_model", route_model_node)

    graph.set_entry_point("understand_intent")
    graph.add_edge("understand_intent", "enrich_context")
    graph.add_edge("enrich_context", "select_tools")
    graph.add_edge("select_tools", "route_model")
    graph.add_edge("route_model", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Module-level cached graph instance
# ---------------------------------------------------------------------------

_preparation_graph: Any = None


def get_preparation_graph() -> Any:
    """Get cached preparation graph (stages 1-4)."""
    global _preparation_graph
    if _preparation_graph is None:
        _preparation_graph = build_preparation_graph()
    return _preparation_graph
