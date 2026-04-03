"""Plugin base class — defines the standard interface for all industry plugins."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PluginTool:
    """Describes a single tool provided by a plugin."""

    name: str
    description: str
    parameters: dict = field(default_factory=dict)  # JSON Schema


@dataclass(frozen=True)
class PluginPromptTemplate:
    """A reusable prompt template shipped with a plugin."""

    name: str
    template: str
    description: str


class PluginBase(ABC):
    """Abstract base for every BridgeAI industry plugin.

    Subclasses MUST set the class-level attributes and implement
    ``get_tools`` / ``execute_tool``.
    """

    name: str = ""
    display_name: str = ""
    description: str = ""
    version: str = "1.0.0"
    category: str = ""  # ecommerce / finance / legal / education

    @abstractmethod
    def get_tools(self) -> list[PluginTool]:
        """Return the list of tools this plugin exposes."""
        ...

    @abstractmethod
    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a named tool with the given arguments.

        Returns a dict with at least ``{"success": bool, "data": ...}``.
        """
        ...

    def get_prompt_templates(self) -> list[PluginPromptTemplate]:
        """Return optional prompt templates shipped with this plugin."""
        return []

    def get_system_prompt_extension(self) -> str:
        """Additional system prompt content when this plugin is active."""
        return ""

    def get_metadata(self) -> dict:
        """Serialise plugin metadata for marketplace listing."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "category": self.category,
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
                for t in self.get_tools()
            ],
            "prompt_templates": [
                {
                    "name": pt.name,
                    "description": pt.description,
                }
                for pt in self.get_prompt_templates()
            ],
        }
