"""MCP Gateway — manages connector lifecycle, routes tool calls, and records audit logs."""

import logging
import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.connectors.base import MCPConnector, ToolResult
from app.mcp.connectors.feishu import FeishuConnector
from app.mcp.connectors.http_api import HttpApiConnector
from app.mcp.connectors.mysql_conn import DatabaseConnector
from app.mcp.masking import mask_dict
from app.models.mcp import McpAuditLog

logger = logging.getLogger(__name__)

# Connector type → class mapping
_CONNECTOR_CLASSES: dict[str, type[MCPConnector]] = {
    "mysql": DatabaseConnector,
    "postgresql": DatabaseConnector,
    "database": DatabaseConnector,
    "http_api": HttpApiConnector,
    "http": HttpApiConnector,
    "feishu": FeishuConnector,
    "lark": FeishuConnector,
}


class MCPGateway:
    """Central gateway that manages MCP connector instances.

    Each registered connector is identified by a ``connector_id`` (usually the
    database UUID of the ``McpConnector`` row).  The gateway keeps live
    connector instances in memory and provides tool routing, health-checking,
    and audit-logging capabilities.
    """

    def __init__(self) -> None:
        # connector_id -> (MCPConnector instance, config dict)
        self._connectors: dict[str, tuple[MCPConnector, dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Connector lifecycle
    # ------------------------------------------------------------------

    async def register_connector(self, connector_id: str, config: dict[str, Any]) -> None:
        """Create and connect an MCP connector instance.

        ``config`` must contain at least ``connector_type`` plus connection
        details (``endpoint_url`` or individual host/port/… fields).
        """
        connector_type = config.get("connector_type", "database")
        cls = _CONNECTOR_CLASSES.get(connector_type)
        if cls is None:
            raise ValueError(f"未知的连接器类型: {connector_type}")

        # If already registered, disconnect the old one first
        if connector_id in self._connectors:
            await self.unregister_connector(connector_id)

        connector = cls()
        await connector.connect(config)
        self._connectors[connector_id] = (connector, config)
        logger.info("Registered MCP connector %s (type=%s)", connector_id, connector_type)

    async def unregister_connector(self, connector_id: str) -> None:
        """Disconnect and remove a connector."""
        entry = self._connectors.pop(connector_id, None)
        if entry is not None:
            connector, _ = entry
            try:
                await connector.disconnect()
            except Exception as exc:
                logger.warning("Error disconnecting connector %s: %s", connector_id, exc)
            logger.info("Unregistered MCP connector %s", connector_id)

    def _get_connector(self, connector_id: str) -> MCPConnector:
        entry = self._connectors.get(connector_id)
        if entry is None:
            raise ValueError(f"连接器 {connector_id} 未注册或已断开")
        return entry[0]

    # ------------------------------------------------------------------
    # Tool operations
    # ------------------------------------------------------------------

    async def execute_tool(
        self,
        connector_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        user_id: str | None = None,
        tenant_id: str | None = None,
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """Route a tool call to the correct connector and record an audit log.

        Returns a dict with keys ``success``, ``data``, ``error``.
        """
        connector = self._get_connector(connector_id)
        start = time.monotonic()

        result: ToolResult | None = None
        error_msg: str | None = None
        try:
            result = await connector.execute_tool(tool_name, arguments)
        except Exception as exc:
            error_msg = str(exc)
            result = ToolResult(success=False, error=error_msg)

        duration_ms = int((time.monotonic() - start) * 1000)

        # Record audit log (best-effort) — original MCP audit log
        if db is not None:
            try:
                audit = McpAuditLog(
                    connector_id=uuid.UUID(connector_id),
                    tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
                    user_id=uuid.UUID(user_id) if user_id else None,
                    action=f"execute_tool:{tool_name}",
                    request_payload={"tool_name": tool_name, "arguments": arguments},
                    response_payload=mask_dict({"success": result.success, "data": result.data}),
                    status="success" if result.success else "error",
                    error_message=result.error,
                    duration_ms=duration_ms,
                )
                db.add(audit)
                await db.flush()
            except Exception as exc:
                logger.warning("Failed to record audit log: %s", exc)

        # Record unified audit log + billing (best-effort)
        if db is not None and tenant_id:
            try:
                from app.services.audit_service import audit_service
                from app.services.billing_service import billing_service

                await audit_service.log_mcp_call(
                    db=db,
                    tenant_id=tenant_id,
                    connector_id=connector_id,
                    agent_id=None,
                    user_id=user_id,
                    action=f"execute_tool:{tool_name}",
                    request_payload={"tool_name": tool_name, "arguments": arguments},
                    response_payload=mask_dict({"success": result.success, "data": result.data}),
                    status="success" if result.success else "error",
                    duration_ms=duration_ms,
                    error_message=result.error,
                )
                await billing_service.record_mcp_usage(
                    db=db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    agent_id=None,
                    connector_id=connector_id,
                    tool_name=tool_name,
                )
            except Exception as exc:
                logger.warning("Failed to record unified audit/billing: %s", exc)

        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "duration_ms": duration_ms,
        }

    async def list_tools(self, connector_id: str) -> list[dict[str, Any]]:
        """List all tools provided by a connector."""
        connector = self._get_connector(connector_id)
        tools = await connector.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in tools
        ]

    async def health_check(self, connector_id: str) -> bool:
        """Check if a connector is healthy."""
        connector = self._get_connector(connector_id)
        return await connector.health_check()

    async def shutdown(self) -> None:
        """Disconnect all connectors (call on app shutdown)."""
        for cid in list(self._connectors.keys()):
            await self.unregister_connector(cid)


# Global singleton — imported by API layer
mcp_gateway = MCPGateway()
