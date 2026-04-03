"""Dynamic plugin loader — discovers plugin modules under industries/."""

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Type

from app.plugins.base import PluginBase

logger = logging.getLogger(__name__)

_INDUSTRIES_PKG = "app.plugins.industries"
_INDUSTRIES_DIR = Path(__file__).parent / "industries"


def discover_plugin_classes() -> list[Type[PluginBase]]:
    """Scan the industries/ directory and return all PluginBase subclasses.

    Each industry package must contain a ``plugin.py`` module that exports
    a concrete subclass of ``PluginBase``.
    """
    found: list[Type[PluginBase]] = []

    if not _INDUSTRIES_DIR.is_dir():
        logger.warning("Industries directory not found: %s", _INDUSTRIES_DIR)
        return found

    for importer, pkg_name, is_pkg in pkgutil.iter_modules([str(_INDUSTRIES_DIR)]):
        if not is_pkg:
            continue
        module_path = f"{_INDUSTRIES_PKG}.{pkg_name}.plugin"
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError:
            logger.debug("No plugin.py in %s, skipping", pkg_name)
            continue
        except Exception as e:
            logger.warning("Failed to import %s: %s", module_path, e)
            continue

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, PluginBase)
                and attr is not PluginBase
                and attr.name  # must have a name set
            ):
                found.append(attr)
                logger.info("Discovered plugin class: %s from %s", attr.name, module_path)

    return found
