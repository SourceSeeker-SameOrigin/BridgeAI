import logging
import re

from app.rag.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class MarkdownParser(BaseParser):
    """Parse Markdown files to plain text by stripping formatting."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".md", ".markdown"]

    def parse(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Strip common markdown syntax but preserve text content
        text = content
        # Remove images ![alt](url)
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
        # Convert links [text](url) to text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        # Remove bold/italic markers
        text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
        text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
        # Remove inline code backticks
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # Remove code block markers (keep content)
        text = re.sub(r"```[a-zA-Z]*\n?", "", text)
        # Convert headers to plain text
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        # Remove horizontal rules
        text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
        # Clean up excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        result = text.strip()
        logger.info("Parsed Markdown %s: %d chars", file_path, len(result))
        return result
