import json
import re
from typing import Any, Dict, List, Optional


# Valid values for enum-like analysis fields
_VALID_EMOTIONS = {"positive", "negative", "confused", "urgent", "neutral"}
_VALID_COMPLEXITIES = {"low", "medium", "high"}


def parse_analysis(content: str) -> Optional[Dict[str, Any]]:
    """
    Parse <analysis> JSON block from LLM response content.

    Expected blueprint fields:
      - emotion: positive | negative | confused | urgent | neutral
      - intent: str (一句话描述用户真实意图)
      - complexity: low | medium | high
      - key_facts: list[str]
      - needs_tool: bool
      - suggested_tools: list[str]

    Also supports legacy fields (confidence, topics) for backward compatibility.
    Returns None if no analysis block is found or if parsing fails.
    """
    pattern = r"<analysis>\s*(.*?)\s*</analysis>"
    match = re.search(pattern, content, re.DOTALL)

    if match is None:
        return None

    raw_json = match.group(1).strip()
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return None

    return normalize_analysis(data)


def normalize_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and validate analysis fields, filling defaults for missing ones.

    Ensures all blueprint fields are present, handles legacy field mappings,
    and constrains enum values to valid sets.
    """
    result: Dict[str, Any] = {}

    # --- emotion ---
    emotion = str(data.get("emotion", "neutral")).lower()
    # Map legacy emotion values to blueprint values
    _emotion_map = {
        "frustrated": "negative",
        "curious": "neutral",
        "excited": "positive",
    }
    emotion = _emotion_map.get(emotion, emotion)
    result["emotion"] = emotion if emotion in _VALID_EMOTIONS else "neutral"

    # --- intent ---
    intent = data.get("intent", "")
    result["intent"] = str(intent) if intent else "general"

    # --- complexity ---
    complexity = str(data.get("complexity", "medium")).lower()
    result["complexity"] = complexity if complexity in _VALID_COMPLEXITIES else "medium"

    # --- key_facts ---
    key_facts = data.get("key_facts")
    if not isinstance(key_facts, list):
        # Fallback: convert legacy 'topics' field if present
        topics = data.get("topics")
        key_facts = list(topics) if isinstance(topics, list) else []
    result["key_facts"] = [str(f) for f in key_facts]

    # --- needs_tool ---
    needs_tool = data.get("needs_tool")
    if isinstance(needs_tool, bool):
        result["needs_tool"] = needs_tool
    else:
        result["needs_tool"] = False

    # --- suggested_tools ---
    suggested_tools = data.get("suggested_tools")
    if not isinstance(suggested_tools, list):
        suggested_tools = []
    result["suggested_tools"] = [str(t) for t in suggested_tools]

    # --- Preserve legacy 'confidence' for backward compatibility with model router ---
    if "confidence" in data:
        try:
            result["confidence"] = float(data["confidence"])
        except (ValueError, TypeError):
            result["confidence"] = 0.5

    return result


def strip_analysis(content: str) -> str:
    """
    Remove <analysis>...</analysis> blocks from content,
    returning clean text for the user.
    """
    pattern = r"<analysis>\s*.*?\s*</analysis>"
    cleaned = re.sub(pattern, "", content, flags=re.DOTALL).strip()
    return cleaned
