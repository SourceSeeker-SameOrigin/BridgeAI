"""Feishu (Lark) MCP connector for messaging, docs, and approvals."""

import logging
from typing import Any

import httpx

from app.mcp.connectors.base import MCPConnector, ToolDefinition, ToolResult
from app.mcp.masking import mask_dict

logger = logging.getLogger(__name__)

# 飞书开放平台 API 基础地址
_FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuConnector(MCPConnector):
    """MCP connector for Feishu (Lark) open platform.

    Supports sending messages, querying documents, and creating approvals
    via the Feishu Open API.  Authenticates using app_id / app_secret to
    obtain a tenant_access_token.
    """

    name = "feishu"
    description = "飞书开放平台（消息、文档、审批）"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._app_id: str = ""
        self._app_secret: str = ""
        self._tenant_access_token: str = ""
        self._timeout: int = 30

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self, config: dict[str, Any]) -> None:
        self._app_id = config.get("app_id", "")
        self._app_secret = config.get("app_secret", "")
        self._timeout = min(config.get("timeout_seconds", 30), 120)

        if not self._app_id or not self._app_secret:
            raise ValueError("飞书连接器需要 app_id 和 app_secret")

        self._client = httpx.AsyncClient(
            base_url=_FEISHU_BASE_URL,
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=True,
        )

        # 获取 tenant_access_token
        await self._refresh_token()

    async def _refresh_token(self) -> None:
        """Obtain or refresh the tenant_access_token."""
        if self._client is None:
            raise RuntimeError("HTTP 客户端未初始化")

        resp = await self._client.post(
            "/auth/v3/tenant_access_token/internal",
            json={"app_id": self._app_id, "app_secret": self._app_secret},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取飞书 token 失败: {data.get('msg', '未知错误')}")
        self._tenant_access_token = data["tenant_access_token"]

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._tenant_access_token}"}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send an authenticated request, auto-retry once on token expiry."""
        if self._client is None:
            raise RuntimeError("飞书客户端未连接")

        resp = await self._client.request(
            method, path, headers=self._auth_headers(), json=json, params=params
        )
        data = resp.json()

        # Token expired → refresh and retry once
        if data.get("code") == 99991663:
            await self._refresh_token()
            resp = await self._client.request(
                method, path, headers=self._auth_headers(), json=json, params=params
            )
            data = resp.json()

        return data

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._tenant_access_token = ""

    async def health_check(self) -> bool:
        if self._client is None:
            return False
        try:
            await self._refresh_token()
            return bool(self._tenant_access_token)
        except Exception as exc:
            logger.warning("Feishu health check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[ToolDefinition]:
        return [
            # ---- 消息 ----
            ToolDefinition(
                name="send_message",
                description="发送飞书消息（支持文本、富文本、卡片）",
                parameters={
                    "type": "object",
                    "properties": {
                        "receive_id": {
                            "type": "string",
                            "description": "接收者 ID（open_id / user_id / union_id / chat_id）",
                        },
                        "receive_id_type": {
                            "type": "string",
                            "enum": ["open_id", "user_id", "union_id", "chat_id"],
                            "description": "接收者 ID 类型",
                            "default": "chat_id",
                        },
                        "msg_type": {
                            "type": "string",
                            "enum": ["text", "post", "interactive"],
                            "description": "消息类型",
                            "default": "text",
                        },
                        "content": {
                            "type": "string",
                            "description": "消息内容（JSON 字符串），文本消息示例: {\"text\":\"hello\"}",
                        },
                    },
                    "required": ["receive_id", "content"],
                },
            ),
            ToolDefinition(
                name="reply_message",
                description="回复飞书消息",
                parameters={
                    "type": "object",
                    "properties": {
                        "message_id": {
                            "type": "string",
                            "description": "被回复的消息 ID",
                        },
                        "msg_type": {
                            "type": "string",
                            "enum": ["text", "post", "interactive"],
                            "description": "消息类型",
                            "default": "text",
                        },
                        "content": {
                            "type": "string",
                            "description": "回复内容（JSON 字符串）",
                        },
                    },
                    "required": ["message_id", "content"],
                },
            ),
            # ---- 文档 ----
            ToolDefinition(
                name="get_document",
                description="获取飞书云文档内容（纯文本）",
                parameters={
                    "type": "object",
                    "properties": {
                        "document_id": {
                            "type": "string",
                            "description": "文档 ID（docx token）",
                        },
                    },
                    "required": ["document_id"],
                },
            ),
            ToolDefinition(
                name="search_documents",
                description="搜索飞书云文档",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词",
                        },
                        "count": {
                            "type": "integer",
                            "description": "返回数量（默认 20，最大 50）",
                            "default": 20,
                        },
                        "doc_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "文档类型过滤，如 [\"docx\", \"sheet\", \"bitable\"]",
                        },
                    },
                    "required": ["query"],
                },
            ),
            ToolDefinition(
                name="list_folder_files",
                description="列出飞书云空间文件夹下的文件",
                parameters={
                    "type": "object",
                    "properties": {
                        "folder_token": {
                            "type": "string",
                            "description": "文件夹 token（为空则列出根目录）",
                            "default": "",
                        },
                        "page_size": {
                            "type": "integer",
                            "description": "每页数量（默认 50）",
                            "default": 50,
                        },
                    },
                },
            ),
            # ---- 审批 ----
            ToolDefinition(
                name="create_approval",
                description="创建飞书审批实例",
                parameters={
                    "type": "object",
                    "properties": {
                        "approval_code": {
                            "type": "string",
                            "description": "审批定义 code（在飞书审批管理后台获取）",
                        },
                        "open_id": {
                            "type": "string",
                            "description": "发起人 open_id",
                        },
                        "form": {
                            "type": "string",
                            "description": "表单数据（JSON 字符串），格式参照审批定义",
                        },
                        "node_approver_open_id_list": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "key": {"type": "string"},
                                    "value": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                            },
                            "description": "各审批节点的审批人（可选，不传则使用审批定义默认值）",
                        },
                    },
                    "required": ["approval_code", "open_id", "form"],
                },
            ),
            ToolDefinition(
                name="get_approval_instance",
                description="查询飞书审批实例详情",
                parameters={
                    "type": "object",
                    "properties": {
                        "instance_id": {
                            "type": "string",
                            "description": "审批实例 ID",
                        },
                    },
                    "required": ["instance_id"],
                },
            ),
            ToolDefinition(
                name="list_approval_instances",
                description="查询飞书审批实例列表",
                parameters={
                    "type": "object",
                    "properties": {
                        "approval_code": {
                            "type": "string",
                            "description": "审批定义 code",
                        },
                        "start_time": {
                            "type": "string",
                            "description": "开始时间（毫秒时间戳）",
                        },
                        "end_time": {
                            "type": "string",
                            "description": "结束时间（毫秒时间戳）",
                        },
                        "page_size": {
                            "type": "integer",
                            "description": "每页数量（默认 20）",
                            "default": 20,
                        },
                    },
                    "required": ["approval_code", "start_time", "end_time"],
                },
            ),
        ]

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        if self._client is None:
            return ToolResult(success=False, error="飞书客户端未连接")

        dispatch = {
            "send_message": self._send_message,
            "reply_message": self._reply_message,
            "get_document": self._get_document,
            "search_documents": self._search_documents,
            "list_folder_files": self._list_folder_files,
            "create_approval": self._create_approval,
            "get_approval_instance": self._get_approval_instance,
            "list_approval_instances": self._list_approval_instances,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return ToolResult(success=False, error=f"未知工具: {tool_name}")

        try:
            result = await handler(arguments)
            masked = mask_dict(result) if isinstance(result, dict) else result
            return ToolResult(success=True, data=masked)
        except httpx.TimeoutException:
            return ToolResult(success=False, error=f"请求超时（{self._timeout}秒）")
        except Exception as exc:
            logger.exception("Feishu tool %s execution failed", tool_name)
            return ToolResult(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # 消息
    # ------------------------------------------------------------------

    async def _send_message(self, args: dict[str, Any]) -> dict[str, Any]:
        receive_id_type = args.get("receive_id_type", "chat_id")
        data = await self._request(
            "POST",
            f"/im/v1/messages?receive_id_type={receive_id_type}",
            json={
                "receive_id": args["receive_id"],
                "msg_type": args.get("msg_type", "text"),
                "content": args["content"],
            },
        )
        if data.get("code") != 0:
            raise RuntimeError(f"发送消息失败: {data.get('msg')}")
        return data.get("data", {})

    async def _reply_message(self, args: dict[str, Any]) -> dict[str, Any]:
        message_id = args["message_id"]
        data = await self._request(
            "POST",
            f"/im/v1/messages/{message_id}/reply",
            json={
                "msg_type": args.get("msg_type", "text"),
                "content": args["content"],
            },
        )
        if data.get("code") != 0:
            raise RuntimeError(f"回复消息失败: {data.get('msg')}")
        return data.get("data", {})

    # ------------------------------------------------------------------
    # 文档
    # ------------------------------------------------------------------

    async def _get_document(self, args: dict[str, Any]) -> dict[str, Any]:
        document_id = args["document_id"]
        data = await self._request(
            "GET",
            f"/docx/v1/documents/{document_id}/raw_content",
        )
        if data.get("code") != 0:
            raise RuntimeError(f"获取文档失败: {data.get('msg')}")
        return data.get("data", {})

    async def _search_documents(self, args: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "search_key": args["query"],
            "count": min(args.get("count", 20), 50),
            "owner_ids": [],
            "chat_ids": [],
            "docs_types": args.get("doc_types"),
        }
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        data = await self._request(
            "POST",
            "/suite/docs-api/search/object",
            json=payload,
        )
        if data.get("code") != 0:
            raise RuntimeError(f"搜索文档失败: {data.get('msg')}")
        return data.get("data", {})

    async def _list_folder_files(self, args: dict[str, Any]) -> dict[str, Any]:
        folder_token = args.get("folder_token", "")
        page_size = min(args.get("page_size", 50), 200)
        path = f"/drive/v1/files?folder_token={folder_token}&page_size={page_size}"
        data = await self._request("GET", path)
        if data.get("code") != 0:
            raise RuntimeError(f"列出文件失败: {data.get('msg')}")
        return data.get("data", {})

    # ------------------------------------------------------------------
    # 审批
    # ------------------------------------------------------------------

    async def _create_approval(self, args: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "approval_code": args["approval_code"],
            "open_id": args["open_id"],
            "form": args["form"],
        }
        approver_list = args.get("node_approver_open_id_list")
        if approver_list:
            payload["node_approver_open_id_list"] = approver_list

        data = await self._request(
            "POST",
            "/approval/v4/instances",
            json=payload,
        )
        if data.get("code") != 0:
            raise RuntimeError(f"创建审批失败: {data.get('msg')}")
        return data.get("data", {})

    async def _get_approval_instance(self, args: dict[str, Any]) -> dict[str, Any]:
        instance_id = args["instance_id"]
        data = await self._request(
            "GET",
            f"/approval/v4/instances/{instance_id}",
        )
        if data.get("code") != 0:
            raise RuntimeError(f"查询审批失败: {data.get('msg')}")
        return data.get("data", {})

    async def _list_approval_instances(self, args: dict[str, Any]) -> dict[str, Any]:
        data = await self._request(
            "GET",
            "/approval/v4/instances",
            params={
                "approval_code": args["approval_code"],
                "start_time": args["start_time"],
                "end_time": args["end_time"],
                "page_size": min(args.get("page_size", 20), 100),
            },
        )
        if data.get("code") != 0:
            raise RuntimeError(f"查询审批列表失败: {data.get('msg')}")
        return data.get("data", {})
