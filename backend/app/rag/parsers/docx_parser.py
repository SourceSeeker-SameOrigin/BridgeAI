import logging

from app.rag.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class DocxParser(BaseParser):
    """Parse DOCX files using python-docx."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".docx"]

    def parse(self, file_path: str) -> str:
        try:
            import docx
        except ImportError as exc:
            raise ImportError("python-docx is required to parse DOCX files: pip install python-docx") from exc

        document = docx.Document(file_path)
        paragraphs: list[str] = []
        for para in document.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)

        result = "\n\n".join(paragraphs)
        logger.info("Parsed DOCX %s: %d paragraphs, %d chars", file_path, len(paragraphs), len(result))
        return result
