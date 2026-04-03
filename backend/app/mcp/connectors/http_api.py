"""HTTP API MCP connector for calling REST APIs."""

import logging
from typing import Any

import httpx

from app.mcp.connectors.base import MCPConnector, ToolDefinition, ToolResult
from app.mcp.masking import mask_dict

logger = logging.getLogger(__name__)


class HttpApiConnector(MCPConnector):
    """Generic MCP connector that lets AI call any REST API."""

    name = "http_api"
    description = "Call REST APIs via HTTP requests"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._base_url: str = ""
        self._headers: dict[str, str] = {}
        self._timeout: int = 30

    async def connect(self, config: dict[str, Any]) -> None:
        endpoint_url = config.get("endpoint_url", "")
        self._base_url = config.get("base_url", endpoint_url).rstrip("/")
        self._headers = config.get("headers", {})
        self._timeout = min(config.get("timeout_seconds", 30), 120)

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=True,
        )

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        if self._client is None:
            return False
        try:
            resp = await self._client.request("HEAD", "/")
            return resp.status_code < 500
        except Exception as exc:
            logger.warning("HTTP API health check failed: %s", exc)
            return False

    async def list_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="http_request",
                description="发起 HTTP 请求（GET/POST/PUT/DELETE）",
                parameters={
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "DELETE"],
                            "description": "HTTP 方法",
                        },
                        "path": {
                            "type": "string",
                            "description": "请求路径（相对于 base_url）",
                        },
                        "headers": {
                            "type": "object",
                            "description": "额外请求头",
                        },
                        "body": {
                            "type": "object",
                            "description": "请求体（JSON）",
                        },
                        "params": {
                            "type": "object",
                            "description": "查询参数",
                        },
                    },
                    "required": ["method", "path"],
                },
            ),
        ]

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        if tool_name != "http_request":
            return ToolResult(success=False, error=f"未知工具: {tool_name}")
        if self._client is None:
            return ToolResult(success=False, error="HTTP 客户端未连接")

        method: str = arguments.get("method", "GET").upper()
        path: str = arguments.get("path", "/")
        headers: dict[str, str] = arguments.get("headers", {})
        body: dict | None = arguments.get("body")
        params: dict | None = arguments.get("params")

        try:
            resp = await self._client.request(
                method=method,
                url=path,
                headers=headers,
                json=body,
                params=params,
            )
            # Try to parse JSON, fall back to text
            try:
                data = resp.json()
            except Exception:
                data = resp.text

            result = {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": data,
            }
            masked = mask_dict(result)
            return ToolResult(success=True, data=masked)
        except httpx.TimeoutException:
            return ToolResult(success=False, error=f"请求超时（{self._timeout}秒）")
        except Exception as exc:
            logger.exception("HTTP request failed")
            return ToolResult(success=False, error=str(exc))
