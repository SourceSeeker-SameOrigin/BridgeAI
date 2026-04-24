"""
Chat Service — LangGraph-powered 6-stage pipeline for LLM conversations.

Architecture:
  Stages 1-4 (preparation) run inside a LangGraph StateGraph:
    1. Intent Understanding — keyword-based pre-classification
    2. Context Enrichment — history + RAG + 4-layer prompt fusion
    3. Tool Selection — resolve and validate MCP tools
    4. Execution Routing — 3-layer model routing

  Stage 5 (Execution) runs outside the graph to support real streaming:
    - Circuit breaker with fallback chain
    - Tool call loop (up to 5 rounds)

  Stage 6 (Output) runs after execution:
    - Parse <analysis> block via post_process_response()
    - Persist messages with intent/emotion metadata
"""

import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.circuit_breaker import get_circuit_breaker
from app.agents.memory import MemoryManager
from app.engine.agent_pipeline import PipelineState, get_preparation_graph, post_process_response
from app.engine.context_parser import strip_analysis
from app.engine.feedback_loop import load_fewshot_examples, store_fewshot_example
from app.mcp.gateway import mcp_gateway
from app.models.agent import Agent
from app.models.conversation import Conversation, Message, MessageEmotion, MessageIntent
from app.models.plugin import InstalledPlugin
from app.models.user import User
from app.plugins.registry import get_plugin_registry
from app.providers.base import LLMResponse, StreamChunk
from app.providers.registry import get_provider_registry
from app.schemas.chat import ChatRequest
from app.services.audit_service import audit_service
from app.services.billing_service import billing_service

logger = logging.getLogger(__name__)

# Default fallback chain (provider, model) when primary model fails
_DEFAULT_FALLBACK_CHAIN: list[tuple[str, str]] = [
    ("deepseek", "deepseek-v4-pro"),
    ("qwen", "qwen-plus"),
    ("anthropic", "claude-sonnet-4-20250514"),
]

_MAX_TOOL_ROUNDS = 100


# ======================================================================
# Public API
# ======================================================================

async def process_chat(
    request: ChatRequest,
    db: AsyncSession,
    user_id: str,
    tenant_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Streaming chat pipeline. Returns SSE event stream."""
    async for event in _run_pipeline(request, db, user_id, tenant_id=tenant_id, stream=True):
        yield event


async def process_chat_sync(
    request: ChatRequest,
    db: AsyncSession,
    user_id: str,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Non-streaming chat pipeline. Returns a complete JSON response dict."""
    result: dict[str, Any] = {}
    async for event in _run_pipeline(request, db, user_id, tenant_id=tenant_id, stream=False):
        if isinstance(event, dict):
            result = event
    return result


# ======================================================================
# Core Pipeline
# ======================================================================

async def _run_pipeline(
    request: ChatRequest,
    db: AsyncSession,
    user_id: str,
    *,
    tenant_id: str | None = None,
    stream: bool = True,
) -> AsyncGenerator[str | dict[str, Any], None]:
    """Core pipeline: LangGraph preparation → LLM execution → persistence."""
    response_id = str(uuid.uuid4())
    start_time = time.monotonic()

    # ── Quota check ─────────────────────────────────────────────────
    if tenant_id:
        allowed, err_msg = await billing_service.check_quota(db, tenant_id)
        if not allowed:
            if stream:
                yield _sse_event({"type": "error", "content": err_msg})
                yield _sse_event({"type": "done"})
                return
            else:
                yield {"code": 429, "message": err_msg, "data": None}
                return

    # ── Stage 0: Load context from DB ────────────────────────────────
    agent, conversation, resolved_tenant_id = await _load_context(
        request, db, user_id, tenant_id=tenant_id,
    )
    conversation_id = str(conversation.id)

    # Load conversation history (last 10 messages)
    history_messages, previous_analysis = await _load_history(db, conversation)

    # Build history dicts for prompt (strip analysis from assistant msgs)
    history_for_prompt: list[dict[str, str]] = []
    for hist_msg in history_messages:
        content = hist_msg.content
        if hist_msg.role == "assistant":
            content = strip_analysis(content)
        history_for_prompt.append({"role": hist_msg.role, "content": content})

    user_content = request.messages[-1].content if request.messages else ""

    # ── SSE: send conversation_id first ──────────────────────────────
    if stream:
        yield _sse_event({
            "type": "meta",
            "conversation_id": conversation_id,
            "response_id": response_id,
        })

    # ── RAG search (async, before graph) ─────────────────────────────
    rag_context = await _search_knowledge_base(db, agent, user_content)

    # ── Resolve MCP tools (async, before graph) ──────────────────────
    available_tools, mcp_connector_ids = await _resolve_mcp_tools(agent)

    # ── Resolve plugin tools for tenant ──────────────────────────────
    plugin_tools, active_plugin_names = await _resolve_plugin_tools(db, resolved_tenant_id)
    if plugin_tools:
        available_tools = list(available_tools) + plugin_tools

    # ── Add delegate_task tool if agent has child agents ─────────────
    has_child_agents = False
    if agent:
        child_check = await db.execute(
            select(Agent.id).where(
                Agent.parent_agent_id == agent.id,
                Agent.is_active.is_(True),
            ).limit(1)
        )
        has_child_agents = child_check.scalar_one_or_none() is not None

    if has_child_agents:
        from app.agents.collaboration import DELEGATE_TOOL
        available_tools = list(available_tools) + [DELEGATE_TOOL]

    # ── Plugin system prompt extension ───────────────────────────────
    plugin_prompt_ext = ""
    if active_plugin_names:
        plugin_registry = get_plugin_registry()
        plugin_prompt_ext = plugin_registry.get_system_prompt_extensions(active_plugin_names)

    # ── Load few-shot examples from Redis ──────────────────────────────
    fewshot_examples: list[dict[str, str]] = []
    if resolved_tenant_id and agent:
        fewshot_examples = await load_fewshot_examples(
            tenant_id=resolved_tenant_id,
            agent_id=str(agent.id),
        )

    # ── Memory: retrieve relevant memories ────────────────────────────
    # ── Memory: retrieve memories scoped to this conversation ──────────
    memory_context = ""
    memory_mgr: MemoryManager | None = None
    if agent and resolved_tenant_id:
        try:
            from app.core.redis import get_redis
            redis_client = await get_redis()
            memory_mgr = MemoryManager(redis_client=redis_client, db_session=db)
            memories = await memory_mgr.retrieve(
                tenant_id=resolved_tenant_id,
                user_id=user_id,
                agent_id=str(agent.id),
                query=user_content,
                top_k=5,
                conversation_id=conversation_id,
            )
            if memories:
                memory_context = "\n\n[用户记忆]\n" + "\n".join(f"- {m}" for m in memories)
        except Exception as e:
            logger.warning("Memory retrieval failed: %s", e)

    # ── Stages 1-4: LangGraph preparation ────────────────────────────
    agent_config = (agent.model_config_ if agent and agent.model_config_ else {}) or {}

    # Merge plugin prompt extension into agent system prompt
    effective_system_prompt = agent.system_prompt if agent else None
    if plugin_prompt_ext:
        if effective_system_prompt:
            effective_system_prompt = f"{effective_system_prompt}\n\n{plugin_prompt_ext}"
        else:
            effective_system_prompt = plugin_prompt_ext

    # Inject memory context into system prompt
    if memory_context:
        if effective_system_prompt:
            effective_system_prompt = f"{effective_system_prompt}\n{memory_context}"
        else:
            effective_system_prompt = memory_context

    initial_state: PipelineState = {
        "user_message": user_content,
        "history_messages": history_for_prompt,
        "agent_system_prompt": effective_system_prompt,
        "agent_config": agent_config,
        "agent_tools": (agent.tools if agent and agent.tools else []) or [],
        "knowledge_base_id": str(agent.knowledge_base_id) if agent and agent.knowledge_base_id else None,
        "request_model": request.model,
        "request_temperature": request.temperature,
        "request_max_tokens": request.max_tokens,
        "previous_analysis": previous_analysis,
        "message_index": len(history_messages),
        "rag_context": rag_context,
        "available_tools": available_tools,
        "mcp_connector_ids": mcp_connector_ids,
        "fewshot_examples": fewshot_examples,
    }

    graph = get_preparation_graph()
    prepared = await graph.ainvoke(initial_state)

    provider_name: str = prepared["provider_name"]
    model_id: str = prepared["model_id"]
    temperature: float = prepared["temperature"]
    max_tokens: int = prepared["max_tokens"]
    optimized_messages: list[dict[str, Any]] = prepared["optimized_messages"]
    tools_for_llm: list[dict[str, Any]] | None = prepared.get("available_tools") or None

    logger.info(
        "Pipeline prepared: provider=%s model=%s reason=%s intent=%s tools=%d",
        provider_name, model_id, prepared.get("routing_reason"),
        prepared.get("intent"), len(tools_for_llm or []),
    )

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        tenant_id=conversation.tenant_id,
        role="user",
        content=user_content,
        model_used=model_id,
    )
    db.add(user_msg)
    await db.flush()

    # ── Stage 5: LLM Execution with tool-call loop ───────────────────
    registry = get_provider_registry()
    circuit_breaker = get_circuit_breaker()

    fallback_chain = [
        (p, m) for p, m in _DEFAULT_FALLBACK_CHAIN
        if not (p == provider_name and m == model_id)
    ]

    if stream:
        # ── Streaming path ───────────────────────────────────────────
        async for event in _execute_streaming(
            registry, circuit_breaker,
            optimized_messages, tools_for_llm,
            provider_name, model_id, fallback_chain,
            temperature, max_tokens,
            mcp_connector_ids, active_plugin_names,
            user_id, resolved_tenant_id, db,
            conversation, start_time, response_id, conversation_id,
            memory_mgr=memory_mgr, agent=agent,
        ):
            yield event
    else:
        # ── Non-streaming path ───────────────────────────────────────
        result = await _execute_sync(
            registry, circuit_breaker,
            optimized_messages, tools_for_llm,
            provider_name, model_id, fallback_chain,
            temperature, max_tokens,
            mcp_connector_ids, active_plugin_names,
            user_id, resolved_tenant_id, db,
            conversation, start_time, response_id, conversation_id,
            memory_mgr=memory_mgr, agent=agent,
        )
        yield result


# ======================================================================
# Streaming Execution (Stage 5 + 6)
# ======================================================================

async def _execute_streaming(
    registry: Any,
    circuit_breaker: Any,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    provider_name: str,
    model_id: str,
    fallback_chain: list[tuple[str, str]],
    temperature: float,
    max_tokens: int,
    mcp_connector_ids: list[str],
    active_plugin_names: list[str],
    user_id: str,
    tenant_id: str | None,
    db: AsyncSession,
    conversation: Conversation,
    start_time: float,
    response_id: str,
    conversation_id: str,
    memory_mgr: Any | None = None,
    agent: Any | None = None,
) -> AsyncGenerator[str, None]:
    """Execute LLM call with streaming + tool-call loop."""
    current_messages = list(messages)
    used_model = model_id
    total_token_in = 0
    total_token_out = 0
    first_token_time: float | None = None
    all_content: list[str] = []

    for tool_round in range(_MAX_TOOL_ROUNDS + 1):
        try:
            used_provider, used_model, llm_result = await circuit_breaker.call_with_fallback(
                provider_getter=registry.get_provider,
                messages=current_messages,
                primary_provider=provider_name,
                primary_model=model_id,
                fallback_chain=fallback_chain,
                stream=True,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except RuntimeError as e:
            error_msg = f"LLM service unavailable: {e}"
            logger.error(error_msg)
            yield _sse_event({"type": "error", "content": error_msg})
            yield _sse_event({"type": "done"})
            await _save_assistant_message(
                db, conversation, error_msg, used_model,
                start_time, None, 0, 0, None,
                response_id=response_id,
            )
            return

        # Consume stream — accumulate content and tool calls
        round_content: list[str] = []
        round_tool_calls: list[dict[str, Any]] = []
        # Accumulator for streaming tool arguments (partial JSON deltas)
        _current_tool_name: str = ""
        _current_tool_args_parts: list[str] = []
        token_in = 0
        token_out = 0

        def _flush_current_tool() -> None:
            """Flush accumulated tool call args into round_tool_calls."""
            nonlocal _current_tool_name, _current_tool_args_parts
            if _current_tool_name:
                args_str = "".join(_current_tool_args_parts)
                try:
                    args = json.loads(args_str) if args_str else {}
                except (json.JSONDecodeError, TypeError):
                    args = {"raw": args_str} if args_str else {}
                round_tool_calls.append({
                    "name": _current_tool_name,
                    "arguments": args,
                })
                _current_tool_name = ""
                _current_tool_args_parts = []

        # Track whether we're inside an <analysis> block so we can
        # suppress those tokens from being sent to the user.
        _in_analysis_block = False
        _analysis_buffer: list[str] = []
        _pending_tag_buffer = ""  # accumulates partial "<analysis" chars

        try:
            async for chunk in llm_result:
                if not isinstance(chunk, StreamChunk):
                    continue

                if chunk.type == "content" and chunk.content:
                    if first_token_time is None:
                        first_token_time = time.monotonic()
                    round_content.append(chunk.content)

                    # ── Filter out <analysis>...</analysis> from user-visible stream ──
                    text = (_pending_tag_buffer + chunk.content) if _pending_tag_buffer else chunk.content
                    _pending_tag_buffer = ""
                    visible_parts: list[str] = []

                    i = 0
                    while i < len(text):
                        if _in_analysis_block:
                            # Look for </analysis>
                            end_idx = text.find("</analysis>", i)
                            if end_idx != -1:
                                _analysis_buffer.append(text[i:end_idx])
                                _in_analysis_block = False
                                i = end_idx + len("</analysis>")
                            else:
                                _analysis_buffer.append(text[i:])
                                i = len(text)
                        else:
                            # Look for <analysis>
                            start_idx = text.find("<analysis>", i)
                            if start_idx != -1:
                                visible_parts.append(text[i:start_idx])
                                _in_analysis_block = True
                                _analysis_buffer = []
                                i = start_idx + len("<analysis>")
                            else:
                                # Check for partial "<analysis" at the end
                                partial_check = text[i:]
                                tag = "<analysis>"
                                found_partial = False
                                for plen in range(min(len(tag) - 1, len(partial_check)), 0, -1):
                                    if partial_check.endswith(tag[:plen]):
                                        visible_parts.append(partial_check[:-plen])
                                        _pending_tag_buffer = partial_check[-plen:]
                                        found_partial = True
                                        break
                                if not found_partial:
                                    visible_parts.append(partial_check)
                                i = len(text)

                    visible_text = "".join(visible_parts)
                    if visible_text:
                        yield _sse_event({"type": "content", "content": visible_text})

                elif chunk.type == "tool_call":
                    # New tool call starting — flush any previous one
                    _flush_current_tool()
                    _current_tool_name = chunk.tool_name
                    _current_tool_args_parts = []
                    yield _sse_event({
                        "type": "tool_call",
                        "name": chunk.tool_name,
                    })

                elif chunk.type == "tool_call_delta":
                    # Partial JSON for current tool's arguments
                    _current_tool_args_parts.append(chunk.content)

                elif chunk.type == "done":
                    # Flush last tool call if any
                    _flush_current_tool()
                    token_in = chunk.token_input
                    token_out = chunk.token_output

        except Exception as e:
            logger.error("Stream error: %s", e, exc_info=True)
            _flush_current_tool()
            yield _sse_event({"type": "error", "content": f"Stream error: {e}"})
            break

        total_token_in += token_in
        total_token_out += token_out
        all_content.extend(round_content)

        # If no tool calls, we're done
        if not round_tool_calls:
            break

        # Execute tool calls via MCP gateway + plugins + delegation
        tool_results = await _execute_tool_calls(
            round_tool_calls, mcp_connector_ids, active_plugin_names, user_id, tenant_id, db,
            parent_agent_id=str(conversation.agent_id) if conversation.agent_id else None,
        )

        # Send tool results to frontend
        for tr in tool_results:
            yield _sse_event({"type": "tool_result", "data": tr})

        # Append assistant message + tool results to messages for next round
        assistant_text = "".join(round_content)
        current_messages.append({"role": "assistant", "content": assistant_text})
        for tr in tool_results:
            current_messages.append({
                "role": "user",
                "content": f"[Tool Result: {tr.get('tool_name', 'unknown')}]\n{json.dumps(tr.get('data', {}), ensure_ascii=False)}",
            })

    # ── Stage 6: Parse analysis & persist ────────────────────────────
    full_content = "".join(all_content)
    analysis, clean_content = post_process_response(full_content)

    # Store key_facts from analysis into memory
    if analysis and memory_mgr and agent and tenant_id:
        key_facts = analysis.get("key_facts", [])
        for fact in key_facts:
            if isinstance(fact, str) and fact.strip():
                try:
                    await memory_mgr.store(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        agent_id=str(agent.id),
                        fact=fact.strip(),
                        importance=analysis.get("confidence", 0.5),
                        conversation_id=conversation_id,
                    )
                except Exception as e:
                    logger.warning("Memory store failed for fact: %s", e)

    # Auto-store high-confidence responses as few-shot examples
    if analysis and analysis.get("confidence", 0) >= 0.85 and tenant_id and agent:
        try:
            # Extract user message from conversation messages
            user_msg_content = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    user_msg_content = m.get("content", "")
                    break
            if user_msg_content and clean_content:
                await store_fewshot_example(
                    tenant_id=tenant_id,
                    agent_id=str(agent.id),
                    user_message=user_msg_content,
                    ai_response=clean_content,
                    rating=4,
                )
        except Exception as e:
            logger.warning("Auto few-shot store failed: %s", e)

    if analysis:
        yield _sse_event({"type": "analysis", "data": analysis})

    yield _sse_event({"type": "done"})

    await _save_assistant_message(
        db, conversation, clean_content, used_model,
        start_time, first_token_time, total_token_in, total_token_out, analysis,
        response_id=response_id,
    )

    # ── Audit & Billing ─────────────────────────────────────────────
    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    if tenant_id:
        await audit_service.log_chat(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=str(conversation.agent_id) if conversation.agent_id else None,
            conversation_id=conversation_id,
            model_used=used_model,
            tokens_in=total_token_in,
            tokens_out=total_token_out,
            duration_ms=elapsed_ms,
        )
        await billing_service.record_chat_usage(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=str(conversation.agent_id) if conversation.agent_id else None,
            model=used_model,
            tokens_in=total_token_in,
            tokens_out=total_token_out,
        )


# ======================================================================
# Non-Streaming Execution (Stage 5 + 6)
# ======================================================================

async def _execute_sync(
    registry: Any,
    circuit_breaker: Any,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    provider_name: str,
    model_id: str,
    fallback_chain: list[tuple[str, str]],
    temperature: float,
    max_tokens: int,
    mcp_connector_ids: list[str],
    active_plugin_names: list[str],
    user_id: str,
    tenant_id: str | None,
    db: AsyncSession,
    conversation: Conversation,
    start_time: float,
    response_id: str,
    conversation_id: str,
    memory_mgr: Any | None = None,
    agent: Any | None = None,
) -> dict[str, Any]:
    """Execute LLM call non-streaming with tool-call loop."""
    current_messages = list(messages)
    used_model = model_id
    total_token_in = 0
    total_token_out = 0

    for tool_round in range(_MAX_TOOL_ROUNDS + 1):
        try:
            used_provider, used_model, llm_result = await circuit_breaker.call_with_fallback(
                provider_getter=registry.get_provider,
                messages=current_messages,
                primary_provider=provider_name,
                primary_model=model_id,
                fallback_chain=fallback_chain,
                stream=False,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except RuntimeError as e:
            error_msg = f"LLM service unavailable: {e}"
            logger.error(error_msg)
            await _save_assistant_message(
                db, conversation, error_msg, used_model,
                start_time, None, 0, 0, None,
                response_id=response_id,
            )
            return _build_sync_response(
                response_id, conversation_id, error_msg, used_model, 0, 0,
            )

        assert isinstance(llm_result, LLMResponse)
        total_token_in += llm_result.token_input
        total_token_out += llm_result.token_output

        # Check for tool calls
        if not llm_result.tool_calls:
            # No tool calls — final response
            full_content = llm_result.content
            analysis, clean_content = post_process_response(full_content)

            await _save_assistant_message(
                db, conversation, clean_content, used_model,
                start_time, time.monotonic(), total_token_in, total_token_out, analysis,
                response_id=response_id,
            )

            # Auto-store high-confidence responses as few-shot examples
            if analysis and analysis.get("confidence", 0) >= 0.85 and tenant_id and agent:
                try:
                    user_msg_content = ""
                    for m in reversed(messages):
                        if m.get("role") == "user":
                            user_msg_content = m.get("content", "")
                            break
                    if user_msg_content and clean_content:
                        await store_fewshot_example(
                            tenant_id=tenant_id,
                            agent_id=str(agent.id),
                            user_message=user_msg_content,
                            ai_response=clean_content,
                            rating=4,
                        )
                except Exception as e:
                    logger.warning("Auto few-shot store failed: %s", e)

            # ── Audit & Billing ─────────────────────────────────────
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            if tenant_id:
                await audit_service.log_chat(
                    db=db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    agent_id=str(conversation.agent_id) if conversation.agent_id else None,
                    conversation_id=conversation_id,
                    model_used=used_model,
                    tokens_in=total_token_in,
                    tokens_out=total_token_out,
                    duration_ms=elapsed_ms,
                )
                await billing_service.record_chat_usage(
                    db=db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    agent_id=str(conversation.agent_id) if conversation.agent_id else None,
                    model=used_model,
                    tokens_in=total_token_in,
                    tokens_out=total_token_out,
                )

            return _build_sync_response(
                response_id, conversation_id, clean_content, used_model,
                total_token_in, total_token_out, analysis,
            )

        # Execute tool calls — providers return flat {"name", "arguments"} format
        tool_calls_parsed = _normalize_tool_calls(llm_result.tool_calls)
        tool_results = await _execute_tool_calls(
            tool_calls_parsed, mcp_connector_ids, active_plugin_names, user_id, tenant_id, db,
            parent_agent_id=str(conversation.agent_id) if conversation.agent_id else None,
        )

        # Append assistant + tool results for next round
        current_messages.append({"role": "assistant", "content": llm_result.content})
        for tr in tool_results:
            current_messages.append({
                "role": "user",
                "content": f"[Tool Result: {tr.get('tool_name', 'unknown')}]\n{json.dumps(tr.get('data', {}), ensure_ascii=False)}",
            })

    # Exhausted tool rounds
    last_content = "工具调用轮次已达上限，请简化请求后重试。"
    await _save_assistant_message(
        db, conversation, last_content, used_model,
        start_time, None, total_token_in, total_token_out, None,
        response_id=response_id,
    )
    return _build_sync_response(
        response_id, conversation_id, last_content, used_model,
        total_token_in, total_token_out,
    )


# ======================================================================
# Tool Call Normalization
# ======================================================================

def _normalize_tool_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize tool_calls from different provider formats.

    Providers return flat format: {"name": "...", "arguments": {...}}
    OpenAI wire format wraps: {"function": {"name": "...", "arguments": "..."}}
    This function handles both.
    """
    result: list[dict[str, Any]] = []
    for tc in tool_calls:
        # Flat format (Anthropic, OpenAICompat after parsing)
        name = tc.get("name", "")
        arguments = tc.get("arguments", {})

        # OpenAI wire format fallback
        if not name and "function" in tc:
            func = tc["function"]
            name = func.get("name", "")
            arguments = func.get("arguments", {})

        # Parse string arguments
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except (json.JSONDecodeError, TypeError):
                arguments = {"raw": arguments}

        if name:
            result.append({"name": name, "arguments": arguments})

    return result


# ======================================================================
# DB Helpers
# ======================================================================

async def _load_context(
    request: ChatRequest,
    db: AsyncSession,
    user_id: str,
    *,
    tenant_id: str | None = None,
) -> tuple[Agent | None, Conversation, str | None]:
    """Load agent and conversation, creating conversation if needed."""
    agent: Agent | None = None
    conversation: Conversation | None = None

    if request.agent_id:
        result = await db.execute(select(Agent).where(Agent.id == request.agent_id))
        agent = result.scalar_one_or_none()

    if request.conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == request.conversation_id)
        )
        conversation = result.scalar_one_or_none()

    # Resolve tenant_id: agent > API param > user's tenant
    resolved_tenant_id = None
    if agent and agent.tenant_id:
        resolved_tenant_id = agent.tenant_id
    elif tenant_id:
        resolved_tenant_id = tenant_id
    else:
        # Fallback: load user's tenant_id
        user_result = await db.execute(select(User.tenant_id).where(User.id == user_id))
        row = user_result.scalar_one_or_none()
        if row:
            resolved_tenant_id = row

    if conversation is None:
        user_msg_preview = ""
        if request.messages:
            user_msg_preview = request.messages[-1].content[:100]
        conversation = Conversation(
            tenant_id=resolved_tenant_id,
            user_id=user_id,
            agent_id=request.agent_id,
            title=user_msg_preview or "New Conversation",
        )
        db.add(conversation)
        await db.flush()

    return agent, conversation, str(resolved_tenant_id) if resolved_tenant_id else None


async def _load_history(
    db: AsyncSession,
    conversation: Conversation,
) -> tuple[list[Any], dict[str, Any] | None]:
    """Load last 10 messages and extract previous analysis."""
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(10)
    )
    history_messages = list(reversed(history_result.scalars().all()))

    previous_analysis: dict[str, Any] | None = None
    for hist_msg in reversed(history_messages):
        if hist_msg.role == "assistant":
            metadata = hist_msg.metadata_
            if isinstance(metadata, dict):
                previous_analysis = metadata.get("analysis")
                if previous_analysis:
                    break

    return history_messages, previous_analysis


async def _save_assistant_message(
    db: AsyncSession,
    conversation: Conversation,
    clean_content: str,
    model_used: str,
    start_time: float,
    first_token_time: float | None,
    token_input: int,
    token_output: int,
    analysis: dict[str, Any] | None,
    response_id: str | None = None,
) -> None:
    """Persist assistant message with analysis metadata.

    When *response_id* is provided, the Message's primary key is set to that
    value so the id returned to the client via the API matches the DB record.
    """
    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    first_ms = int((first_token_time - start_time) * 1000) if first_token_time else None

    intent = analysis.get("intent") if analysis else None
    emotion = analysis.get("emotion") if analysis else None
    metadata = {"analysis": analysis} if analysis else {}

    assistant_msg = Message(
        conversation_id=conversation.id,
        tenant_id=conversation.tenant_id,
        role="assistant",
        content=clean_content,
        model_used=model_used,
        response_time_ms=elapsed_ms,
        first_token_ms=first_ms,
        token_input=token_input,
        token_output=token_output,
        intent=intent,
        emotion=emotion,
        metadata_=metadata,
    )
    if response_id:
        assistant_msg.id = response_id
    db.add(assistant_msg)
    await db.flush()

    # Save structured intent/emotion records for detailed analytics
    if analysis:
        confidence = analysis.get("confidence", 0.0)
        if intent:
            db.add(MessageIntent(
                message_id=assistant_msg.id,
                intent=intent,
                confidence=confidence,
            ))
        if emotion:
            db.add(MessageEmotion(
                message_id=assistant_msg.id,
                emotion=emotion,
                confidence=confidence,
            ))
        await db.flush()


# ======================================================================
# RAG Integration
# ======================================================================

async def _search_knowledge_base(
    db: AsyncSession,
    agent: Agent | None,
    user_message: str,
) -> str | None:
    """Search agent's knowledge base for relevant context."""
    if not agent or not agent.knowledge_base_id:
        return None

    try:
        from app.rag.engine import RAGEngine

        rag = RAGEngine(db)
        results = await rag.search(
            knowledge_base_id=str(agent.knowledge_base_id),
            query=user_message,
            top_k=3,
        )
        if not results:
            return None

        # Format RAG results as context string
        context_parts: list[str] = []
        for i, r in enumerate(results, 1):
            context_parts.append(f"[{i}] (相关度: {r.similarity:.2f})\n{r.content}")

        return "\n\n".join(context_parts)

    except Exception as e:
        logger.warning("RAG search failed: %s", e)
        return None


# ======================================================================
# Plugin Tool Integration
# ======================================================================

async def _resolve_plugin_tools(
    db: AsyncSession,
    tenant_id: str | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve installed plugin tools for a tenant.

    Returns (openai_format_tools, active_plugin_names).
    """
    if not tenant_id:
        return [], []

    try:
        result = await db.execute(
            select(InstalledPlugin.plugin_name).where(
                InstalledPlugin.tenant_id == tenant_id,
                InstalledPlugin.is_active.is_(True),
            )
        )
        plugin_names = [row[0] for row in result.all()]
    except Exception as e:
        logger.warning("Failed to load installed plugins: %s", e)
        return [], []

    if not plugin_names:
        return [], []

    plugin_registry = get_plugin_registry()
    tools = plugin_registry.get_tools_for_plugins(plugin_names)
    return tools, plugin_names


# ======================================================================
# MCP Tool Integration
# ======================================================================

async def _resolve_mcp_tools(
    agent: Agent | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve MCP connector tools for the agent.

    Returns (openai_format_tools, connector_ids).
    """
    if not agent or not agent.tools:
        return [], []

    connector_ids: list[str] = []
    all_tools: list[dict[str, Any]] = []

    for connector_id in agent.tools:
        if not isinstance(connector_id, str):
            continue
        try:
            tools = await mcp_gateway.list_tools(connector_id)
            connector_ids.append(connector_id)
            for tool in tools:
                all_tools.append({
                    "type": "function",
                    "function": {
                        "name": f"{connector_id[:8]}_{tool['name']}",
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                    },
                    "_connector_id": connector_id,
                    "_original_name": tool["name"],
                })
        except Exception as e:
            logger.warning("Failed to list tools for connector %s: %s", connector_id, e)

    return all_tools, connector_ids


async def _execute_tool_calls(
    tool_calls: list[dict[str, Any]],
    mcp_connector_ids: list[str],
    active_plugin_names: list[str],
    user_id: str,
    tenant_id: str | None,
    db: AsyncSession,
    *,
    parent_agent_id: str | None = None,
    delegation_depth: int = 0,
) -> list[dict[str, Any]]:
    """Execute tool calls via MCP gateway, plugin registry, or agent delegation."""
    results: list[dict[str, Any]] = []
    plugin_registry = get_plugin_registry() if active_plugin_names else None

    for tc in tool_calls:
        tool_name = tc.get("name", "")
        arguments = tc.get("arguments", {})

        # Parse arguments if they're a string
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except (json.JSONDecodeError, TypeError):
                arguments = {"raw": arguments}

        # Check for delegate_task tool (multi-agent collaboration)
        if tool_name == "delegate_task" or tool_name.endswith("_delegate_task"):
            if parent_agent_id:
                try:
                    from app.agents.collaboration import get_collaborator
                    collaborator = get_collaborator()
                    delegation_result = await collaborator.delegate_by_name(
                        parent_agent_id=parent_agent_id,
                        child_name_or_key=arguments.get("child_agent_name", ""),
                        task_description=arguments.get("task", ""),
                        context={"context": arguments.get("context", "")},
                        db=db,
                        depth=delegation_depth + 1,
                    )
                    results.append({
                        "tool_name": tool_name,
                        "success": delegation_result.success,
                        "data": delegation_result.to_dict(),
                        "error": delegation_result.error,
                    })
                except Exception as e:
                    logger.error("Delegate task error: %s", e, exc_info=True)
                    results.append({
                        "tool_name": tool_name,
                        "success": False,
                        "error": str(e),
                        "data": None,
                    })
            else:
                results.append({
                    "tool_name": tool_name,
                    "success": False,
                    "error": "当前Agent没有配置父Agent关系，无法委派任务",
                    "data": None,
                })
            continue

        # Check if this is a plugin tool (prefix: plugin_{name}_{tool})
        plugin_match = _match_plugin_tool(tool_name, active_plugin_names)
        if plugin_match and plugin_registry:
            pname, original_tool = plugin_match
            try:
                plugin = plugin_registry.get_plugin(pname)
                result = await plugin.execute_tool(original_tool, arguments)
                results.append({
                    "tool_name": tool_name,
                    "success": result.get("success", False),
                    "data": result.get("data"),
                    "error": result.get("error"),
                })
            except Exception as e:
                logger.error("Plugin tool execution error for %s: %s", tool_name, e)
                results.append({
                    "tool_name": tool_name,
                    "success": False,
                    "error": str(e),
                    "data": None,
                })
            continue

        # Find which MCP connector owns this tool (prefix-based)
        connector_id = None
        original_name = tool_name
        for cid in mcp_connector_ids:
            prefix = f"{cid[:8]}_"
            if tool_name.startswith(prefix):
                connector_id = cid
                original_name = tool_name[len(prefix):]
                break

        if not connector_id:
            results.append({
                "tool_name": tool_name,
                "success": False,
                "error": f"No connector found for tool: {tool_name}",
                "data": None,
            })
            continue

        try:
            result = await mcp_gateway.execute_tool(
                connector_id=connector_id,
                tool_name=original_name,
                arguments=arguments,
                user_id=user_id,
                tenant_id=tenant_id,
                db=db,
            )
            results.append({
                "tool_name": tool_name,
                "success": result.get("success", False),
                "data": result.get("data"),
                "error": result.get("error"),
            })
        except Exception as e:
            logger.error("Tool execution error for %s: %s", tool_name, e)
            results.append({
                "tool_name": tool_name,
                "success": False,
                "error": str(e),
                "data": None,
            })

    return results


def _match_plugin_tool(
    tool_name: str, active_plugin_names: list[str]
) -> tuple[str, str] | None:
    """Match a tool name to a plugin.

    Plugin tools are named ``plugin_{plugin_name}_{tool_name}``.
    Returns (plugin_name, original_tool_name) or None.
    """
    if not tool_name.startswith("plugin_"):
        return None
    remainder = tool_name[len("plugin_"):]
    for pname in active_plugin_names:
        prefix = f"{pname}_"
        if remainder.startswith(prefix):
            return pname, remainder[len(prefix):]
    return None


# ======================================================================
# SSE / Response Formatting
# ======================================================================

def _sse_event(data: dict[str, Any]) -> str:
    """Format an SSE event line."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_sync_response(
    response_id: str,
    conversation_id: str,
    content: str,
    model: str,
    token_input: int,
    token_output: int,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a non-streaming JSON response dict.

    Returns a flat structure with ``content``, ``conversation_id``, etc.
    """
    resp: dict[str, Any] = {
        "content": content,
        "conversation_id": conversation_id,
        "model": model,
        "id": response_id,
        "usage": {
            "prompt_tokens": token_input,
            "completion_tokens": token_output,
            "total_tokens": token_input + token_output,
        },
    }
    if analysis:
        resp["analysis"] = analysis
    return resp
