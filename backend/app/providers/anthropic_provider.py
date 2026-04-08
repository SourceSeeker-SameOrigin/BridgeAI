"""Anthropic Claude provider using direct HTTP API (httpx)."""

import json
import logging
from typing import Any, AsyncGenerator

import httpx
from httpx_sse import aconnect_sse

from app.providers.base import LLMProvider, LLMResponse, StreamChunk

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def _convert_messages_for_anthropic(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    """
    Anthropic API requires system prompt as a separate top-level param,
    not as a message. Extract it and return (system, messages).
    """
    system_text: str | None = None
    api_messages: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            # Concatenate multiple system messages
            if system_text is None:
                system_text = content
            else:
                system_text = f"{system_text}\n\n{content}"
        else:
            # Map 'assistant' stays 'assistant', 'user' stays 'user'
            api_messages.append({"role": role, "content": content})

    return system_text, api_messages


def _build_tools_for_anthropic(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI-style tool defs to Anthropic format."""
    anthropic_tools: list[dict[str, Any]] = []
    for tool in tools:
        if tool.get("type") == "function":
            func = tool["function"]
            anthropic_tools.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            })
        elif "name" in tool and "input_schema" in tool:
            # Already in Anthropic format
            anthropic_tools.append(tool)
    return anthropic_tools


class AnthropicProvider(LLMProvider):
    """Claude provider via Anthropic Messages API."""

    provider_name = "anthropic"

    def __init__(self, api_key: str, proxy_url: str | None = None) -> None:
        self._api_key = api_key
        # Overseas API, use system proxy by default
        transport = None
        if proxy_url:
            transport = httpx.AsyncHTTPTransport(proxy=proxy_url)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=30.0),
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

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
        system_text, api_messages = _convert_messages_for_anthropic(messages)

        body: dict[str, Any] = {
            "model": model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_text:
            body["system"] = system_text
        if tools:
            body["tools"] = _build_tools_for_anthropic(tools)
        if stream:
            body["stream"] = True

        if stream:
            return self._stream_chat(body)
        return await self._non_stream_chat(body)

    async def _non_stream_chat(self, body: dict[str, Any]) -> LLMResponse:
        resp = await self._client.post(
            ANTHROPIC_API_URL,
            headers=self._headers(),
            json=body,
        )
        if resp.status_code != 200:
            error_text = resp.text
            logger.error("Anthropic API error %d: %s", resp.status_code, error_text)
            raise RuntimeError(f"Anthropic API error {resp.status_code}: {error_text}")

        data = resp.json()
        # Extract content blocks
        content_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for block in data.get("content", []):
            if block.get("type") == "text":
                content_parts.append(block["text"])
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "name": block["name"],
                    "arguments": block.get("input", {}),
                    "id": block.get("id", ""),
                })

        usage = data.get("usage", {})
        return LLMResponse(
            content="".join(content_parts),
            model=data.get("model", body.get("model", "")),
            finish_reason=data.get("stop_reason", "stop"),
            token_input=usage.get("input_tokens", 0),
            token_output=usage.get("output_tokens", 0),
            tool_calls=tool_calls,
        )

    async def _stream_chat(self, body: dict[str, Any]) -> AsyncGenerator[StreamChunk, None]:
        async with aconnect_sse(
            self._client, "POST", ANTHROPIC_API_URL,
            headers=self._headers(),
            json=body,
        ) as event_source:
            token_input = 0
            token_output = 0

            async for event in event_source.aiter_sse():
                event_type = event.event
                if event.data.strip() == "":
                    continue

                try:
                    data = json.loads(event.data)
                except json.JSONDecodeError:
                    continue

                if event_type == "message_start":
                    usage = data.get("message", {}).get("usage", {})
                    token_input = usage.get("input_tokens", 0)

                elif event_type == "content_block_delta":
                    delta = data.get("delta", {})
                    delta_type = delta.get("type", "")
                    if delta_type == "text_delta":
                        yield StreamChunk(type="content", content=delta.get("text", ""))
                    elif delta_type == "input_json_delta":
                        # Tool use streaming - partial JSON
                        yield StreamChunk(
                            type="tool_call_delta",
                            content=delta.get("partial_json", ""),
                        )

                elif event_type == "content_block_start":
                    block = data.get("content_block", {})
                    if block.get("type") == "tool_use":
                        yield StreamChunk(
                            type="tool_call",
                            tool_name=block.get("name", ""),
                            tool_arguments={},
                        )

                elif event_type == "message_delta":
                    usage = data.get("usage", {})
                    token_output = usage.get("output_tokens", 0)
                    stop_reason = data.get("delta", {}).get("stop_reason", "stop")
                    yield StreamChunk(
                        type="done",
                        finish_reason=stop_reason,
                        token_input=token_input,
                        token_output=token_output,
                    )

                elif event_type == "message_stop":
                    pass  # Already handled via message_delta

                elif event_type == "error":
                    error_msg = data.get("error", {}).get("message", "Unknown error")
                    logger.error("Anthropic stream error: %s", error_msg)
                    raise RuntimeError(f"Anthropic stream error: {error_msg}")

    async def health_check(self) -> bool:
        try:
            # Simple check: make a minimal request
            resp = await self._client.post(
                ANTHROPIC_API_URL,
                headers=self._headers(),
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning("Anthropic health check failed: %s", e)
            return False
