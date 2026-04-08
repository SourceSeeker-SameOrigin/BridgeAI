"""Generic OpenAI-compatible provider (works with DeepSeek, Qwen, Ollama, etc.)."""

import json
import logging
from typing import Any, AsyncGenerator

import httpx
from httpx_sse import aconnect_sse

from app.providers.base import LLMProvider, LLMResponse, StreamChunk

logger = logging.getLogger(__name__)


class OpenAICompatProvider(LLMProvider):
    """
    Generic provider for any OpenAI-compatible API.
    Supports: DeepSeek, Qwen/DashScope, local Ollama, vLLM, etc.
    """

    provider_name = "openai_compat"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        provider_name: str = "openai_compat",
        proxy_url: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self.provider_name = provider_name

        transport = None
        if proxy_url:
            transport = httpx.AsyncHTTPTransport(proxy=proxy_url)

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=30.0),
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    @property
    def _chat_url(self) -> str:
        return f"{self._base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
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
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
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
            logger.error(
                "%s API error %d: %s",
                self.provider_name, resp.status_code, error_text,
            )
            raise RuntimeError(
                f"{self.provider_name} API error {resp.status_code}: {error_text}"
            )

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
        # Pre-flight: send request manually to handle non-SSE error responses
        response = await self._client.send(
            self._client.build_request("POST", self._chat_url, headers=self._headers(), json=body),
            stream=True,
        )
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            # LLM API returned a JSON error (auth failure, quota, etc.)
            error_body = await response.aread()
            await response.aclose()
            try:
                err_data = json.loads(error_body)
                err_msg = err_data.get("error", {}).get("message", "") or err_data.get("message", "") or str(err_data)
            except Exception:
                err_msg = error_body.decode(errors="replace")[:200]
            raise RuntimeError(f"LLM API error ({response.status_code}): {err_msg}")

        from httpx_sse import EventSource
        event_source = EventSource(response)
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
                await response.aclose()
                return
            if not raw:
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # Extract usage if present (some providers include in last chunk)
            chunk_usage = data.get("usage", {})
            if chunk_usage:
                token_input = chunk_usage.get("prompt_tokens", token_input)
                token_output = chunk_usage.get("completion_tokens", token_output)

            choice = data.get("choices", [{}])[0]
            delta = choice.get("delta", {})
            finish_reason = choice.get("finish_reason")

            # Content delta
            content = delta.get("content")
            if content:
                yield StreamChunk(type="content", content=content)

            # Tool call delta
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
        await response.aclose()

    async def health_check(self) -> bool:
        try:
            # Try listing models endpoint
            resp = await self._client.get(
                f"{self._base_url}/models",
                headers=self._headers(),
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning("%s health check failed: %s", self.provider_name, e)
            return False
