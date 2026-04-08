"""Plugin registry — discovers, registers and manages plugin instances."""

import logging
from typing import Any

from app.plugins.base import PluginBase, PluginTool

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Singleton registry that manages all available plugin instances."""

    def __init__(self) -> None:
        self._plugins: dict[str, PluginBase] = {}
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._auto_discover()

    def _auto_discover(self) -> None:
        """Import and register all built-in industry plugins via the loader."""
        from app.plugins.loader import discover_plugin_classes

        for plugin_cls in discover_plugin_classes():
            try:
                plugin = plugin_cls()
                self._plugins[plugin.name] = plugin
                logger.info("Registered plugin: %s (v%s)", plugin.name, plugin.version)
            except Exception as e:
                logger.warning("Failed to instantiate plugin %s: %s", plugin_cls.name, e)

    def register(self, plugin: PluginBase) -> None:
        """Manually register a plugin instance."""
        self._plugins[plugin.name] = plugin
        logger.info("Manually registered plugin: %s", plugin.name)

    def get_plugin(self, name: str) -> PluginBase:
        """Get a plugin by name.

        Raises:
            ValueError: If plugin is not found.
        """
        self._ensure_initialized()
        plugin = self._plugins.get(name)
        if plugin is None:
            available = list(self._plugins.keys())
            raise ValueError(
                f"Plugin '{name}' not found. Available: {available}"
            )
        return plugin

    def list_plugins(self) -> list[dict[str, Any]]:
        """Return metadata for all registered plugins."""
        self._ensure_initialized()
        return [p.get_metadata() for p in self._plugins.values()]

    def get_tools_for_plugins(self, plugin_names: list[str]) -> list[dict[str, Any]]:
        """Get merged OpenAI-format tool definitions from the given plugins.

        Returns a list of tool dicts ready for the LLM function-calling context.
        """
        self._ensure_initialized()
        tools: list[dict[str, Any]] = []
        for pname in plugin_names:
            plugin = self._plugins.get(pname)
            if plugin is None:
                continue
            for t in plugin.get_tools():
                tools.append({
                    "type": "function",
                    "function": {
                        "name": f"plugin_{pname}_{t.name}",
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                    "_plugin_name": pname,
                    "_original_tool_name": t.name,
                })
        return tools

    def get_system_prompt_extensions(self, plugin_names: list[str]) -> str:
        """Concatenate system prompt extensions for active plugins."""
        self._ensure_initialized()
        parts: list[str] = []
        for pname in plugin_names:
            plugin = self._plugins.get(pname)
            if plugin is None:
                continue
            ext = plugin.get_system_prompt_extension()
            if ext:
                parts.append(ext)
        return "\n\n".join(parts)

    def list_plugin_names(self) -> list[str]:
        """Return the names of all registered plugins."""
        self._ensure_initialized()
        return list(self._plugins.keys())


# Module-level singleton
_registry: PluginRegistry | None = None


def get_plugin_registry() -> PluginRegistry:
    """Get the global plugin registry singleton."""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry
