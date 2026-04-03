import logging

from app.rag.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class TextParser(BaseParser):
    """Passthrough parser for plain text files."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".txt", ".text", ".csv", ".log", ".json", ".xml", ".yaml", ".yml"]

    def parse(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        result = content.strip()
        logger.info("Parsed text file %s: %d chars", file_path, len(result))
        return result
