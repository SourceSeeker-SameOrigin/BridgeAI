"""
Sensitive content filter middleware using DFA (Deterministic Finite Automaton).

Uses an Aho-Corasick-style trie for efficient multi-pattern matching.
Loads sensitive words from a configurable text file.

Applied only to chat-related endpoints (POST /api/v1/chat/*).
"""

import json
import logging
from pathlib import Path
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

_DEFAULT_WORD_FILE = Path(__file__).parent / "sensitive_words.txt"

# Paths where content filtering is applied (prefix match)
_FILTERED_PATH_PREFIXES = ("/api/v1/chat",)


class _DFANode:
    """Trie node for DFA-based sensitive word detection."""

    __slots__ = ("children", "is_end", "word")

    def __init__(self) -> None:
        self.children: dict[str, "_DFANode"] = {}
        self.is_end: bool = False
        self.word: str = ""


class SensitiveWordFilter:
    """DFA trie for fast multi-pattern sensitive word detection."""

    def __init__(self) -> None:
        self._root = _DFANode()
        self._word_count = 0

    def load_from_file(self, filepath: str | Path) -> None:
        """Load sensitive words from a text file (one word per line)."""
        path = Path(filepath)
        if not path.exists():
            logger.warning("Sensitive word file not found: %s", filepath)
            return

        count = 0
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word and not word.startswith("#"):
                    self._add_word(word)
                    count += 1

        self._word_count = count
        logger.info("Loaded %d sensitive words from %s", count, filepath)

    def _add_word(self, word: str) -> None:
        """Insert a word into the DFA trie."""
        node = self._root
        for char in word:
            if char not in node.children:
                node.children[char] = _DFANode()
            node = node.children[char]
        node.is_end = True
        node.word = word

    def detect(self, text: str) -> list[str]:
        """Detect all sensitive words in the text.

        Returns a list of matched sensitive words (deduplicated).
        """
        if not text or self._word_count == 0:
            return []

        found: list[str] = []
        seen: set[str] = set()

        for i in range(len(text)):
            node = self._root
            j = i
            while j < len(text) and text[j] in node.children:
                node = node.children[text[j]]
                if node.is_end and node.word not in seen:
                    found.append(node.word)
                    seen.add(node.word)
                j += 1

        return found

    @property
    def word_count(self) -> int:
        return self._word_count


# Module-level singleton
_filter_instance: SensitiveWordFilter | None = None


def get_word_filter() -> SensitiveWordFilter:
    """Get or initialize the global sensitive word filter."""
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = SensitiveWordFilter()
        _filter_instance.load_from_file(_DEFAULT_WORD_FILE)
    return _filter_instance


class ContentFilterMiddleware(BaseHTTPMiddleware):
    """Middleware that checks user input for sensitive content.

    Only applies to POST requests on chat endpoints.
    Reads the request body, scans for sensitive words, and returns
    a 400 response if any are found.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Only filter POST requests on chat paths
        if request.method != "POST":
            return await call_next(request)

        path = request.url.path.rstrip("/") or "/"
        if not any(path.startswith(prefix) for prefix in _FILTERED_PATH_PREFIXES):
            return await call_next(request)

        # Read and inspect body
        body = await request.body()
        if not body:
            return await call_next(request)

        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return await call_next(request)

        # Extract user text to check
        text_to_check = self._extract_user_text(payload)
        if not text_to_check:
            return await call_next(request)

        word_filter = get_word_filter()
        matches = word_filter.detect(text_to_check)

        if matches:
            logger.warning(
                "Sensitive content detected from %s: %s",
                request.client.host if request.client else "unknown",
                matches,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "code": 400,
                    "message": "输入内容包含敏感词汇，请修改后重试",
                    "data": {"matched_count": len(matches)},
                },
            )

        return await call_next(request)

    def _extract_user_text(self, payload: dict[str, Any]) -> str:
        """Extract the user's message text from the chat request payload."""
        parts: list[str] = []

        # Direct message field
        message = payload.get("message", "")
        if isinstance(message, str) and message:
            parts.append(message)

        # Messages array (last message)
        messages = payload.get("messages", [])
        if isinstance(messages, list):
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, str) and content:
                        parts.append(content)

        return " ".join(parts)
