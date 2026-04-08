"""Ollama local model provider.

Ollama serves models locally via an OpenAI-compatible API.
Local service — no auth, no proxy.
"""

import json
import logging
from typing import Any, AsyncGenerator

import httpx
from httpx_sse import aconnect_sse

from app.providers.base import LLMProvider, LLMResponse, StreamChunk

logger = logging.getLogger(__name__)

OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider(LLMProvider):
    """
    Ollama local model provider.

    Uses Ollama's OpenAI-compatible API at /v1/chat/completions.
    No authentication required. Local service — no proxy.
    Models depend on what is installed locally (e.g., llama3, qwen2, mistral).
    """

    provider_name = "ollama"

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or OLLAMA_DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=10.0),  # Local models can be slow
        )

    async def close(self) -> None:
        await self._client.aclose()

    @property
    def _chat_url(self) -> str:
        return f"{self._base_url}/v1/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

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
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        # Ollama OpenAI-compat supports max_tokens as num_predict option
        if max_tokens:
            body["max_tokens"] = max_tokens
        if tools:
            body["tools"] = tools

        if stream:
            return self._stream_chat(body)
        return await self._non_stream_chat(body)

    async def _non_stream_chat(self, body: dict[str, Any]) -> LLMResponse:
        resp = await self._client.post(
            self._chat_url,
            headers=self._headers(),
            json=body,
        )
        if resp.status_code != 200:
            error_text = resp.text
            logger.error("Ollama API error %d: %s", resp.status_code, error_text)
            raise RuntimeError(f"Ollama API error {resp.status_code}: {error_text}")

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""

        tool_calls: list[dict[str, Any]] = []
        for tc in message.get("tool_calls", []):
            func = tc.get("function", {})
            args_str = func.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {"raw": args_str}
            tool_calls.append({
                "name": func.get("name", ""),
                "arguments": args,
                "id": tc.get("id", ""),
            })

        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            model=data.get("model", body.get("model", "")),
            finish_reason=choice.get("finish_reason", "stop"),
            token_input=usage.get("prompt_tokens", 0),
            token_output=usage.get("completion_tokens", 0),
            tool_calls=tool_calls,
        )

    async def _stream_chat(self, body: dict[str, Any]) -> AsyncGenerator[StreamChunk, None]:
        async with aconnect_sse(
            self._client, "POST", self._chat_url,
            headers=self._headers(),
            json=body,
        ) as event_source:
            token_input = 0
            token_output = 0

            async for event in event_source.aiter_sse():
                raw = event.data.strip()
                if raw == "[DONE]":
                    yield StreamChunk(
                        type="done",
                        finish_reason="stop",
                        token_input=token_input,
                        token_output=token_output,
                    )
                    return
                if not raw:
                    continue

                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                chunk_usage = data.get("usage", {})
                if chunk_usage:
                    token_input = chunk_usage.get("prompt_tokens", token_input)
                    token_output = chunk_usage.get("completion_tokens", token_output)

                choice = data.get("choices", [{}])[0]
                delta = choice.get("delta", {})
                finish_reason = choice.get("finish_reason")

                content = delta.get("content")
                if content:
                    yield StreamChunk(type="content", content=content)

                tool_calls = delta.get("tool_calls", [])
                for tc in tool_calls:
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    args_str = func.get("arguments", "")
                    if name:
                        yield StreamChunk(type="tool_call", tool_name=name)
                    if args_str:
                        yield StreamChunk(type="tool_call_delta", content=args_str)

                if finish_reason:
                    yield StreamChunk(
                        type="done",
                        finish_reason=finish_reason,
                        token_input=token_input,
                        token_output=token_output,
                    )

    async def health_check(self) -> bool:
        """Check if Ollama is running by hitting the /api/tags endpoint."""
        try:
            resp = await self._client.get(f"{self._base_url}/api/tags")
            return resp.status_code == 200
        except Exception as e:
            logger.warning("Ollama health check failed: %s", e)
            return False
