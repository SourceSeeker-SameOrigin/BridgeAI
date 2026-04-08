"""Sensitive data masking utilities for MCP tool results."""

import re
from typing import Any


MASKING_RULES: list[dict[str, Any]] = [
    {
        "name": "手机号",
        "pattern": r"1[3-9]\d{9}",
        "replacement": lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:],
    },
    {
        "name": "身份证",
        "pattern": r"\d{17}[\dXx]",
        "replacement": "***身份证***",
    },
    {
        "name": "银行卡",
        "pattern": r"\d{16,19}",
        "replacement": "***银行卡***",
    },
    {
        "name": "邮箱",
        "pattern": r"[\w.]+@[\w.]+\.\w+",
        "replacement": "***邮箱***",
    },
]

# Pre-compile patterns for performance
_COMPILED_RULES: list[tuple[str, re.Pattern, Any]] = [
    (rule["name"], re.compile(rule["pattern"]), rule["replacement"])
    for rule in MASKING_RULES
]


def mask_sensitive_data(text: str) -> str:
    """Apply all masking rules to the given text.

    Rules are applied in order: phone > ID card > bank card > email.
    This order matters because shorter numeric patterns could match
    substrings of longer ones.
    """
    if not isinstance(text, str):
        return text
    result = text
    for _name, pattern, replacement in _COMPILED_RULES:
        if callable(replacement):
            result = pattern.sub(replacement, result)
        else:
            result = pattern.sub(replacement, result)
    return result


def mask_dict(data: Any) -> Any:
    """Recursively mask sensitive data in dicts, lists, and strings."""
    if isinstance(data, str):
        return mask_sensitive_data(data)
    if isinstance(data, dict):
        return {k: mask_dict(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [mask_dict(item) for item in data]
    return data
