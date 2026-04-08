"""Abstract base class for MCP connectors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    """Definition of a tool exposed by an MCP connector."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """Result returned from executing an MCP tool."""

    success: bool
    data: Any = None
    error: str | None = None


class MCPConnector(ABC):
    """Abstract base class that all MCP connectors must implement."""

    name: str = ""
    description: str = ""

    @abstractmethod
    async def connect(self, config: dict[str, Any]) -> None:
        """Establish connection using the provided configuration."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection and release resources."""

    @abstractmethod
    async def list_tools(self) -> list[ToolDefinition]:
        """Return the list of tools this connector provides."""

    @abstractmethod
    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with the given arguments."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the connector is healthy and connected."""
