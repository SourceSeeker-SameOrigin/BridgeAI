"""Plugin framework for BridgeAI industry plugins."""

from app.plugins.base import PluginBase, PluginPromptTemplate, PluginTool
from app.plugins.registry import get_plugin_registry, PluginRegistry

__all__ = [
    "PluginBase",
    "PluginTool",
    "PluginPromptTemplate",
    "PluginRegistry",
    "get_plugin_registry",
]
