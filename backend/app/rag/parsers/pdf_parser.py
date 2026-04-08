import logging

from app.rag.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class PdfParser(BaseParser):
    """Parse PDF files using PyPDF2."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    def parse(self, file_path: str) -> str:
        try:
            from PyPDF2 import PdfReader
        except ImportError as exc:
            raise ImportError("PyPDF2 is required to parse PDF files: pip install PyPDF2") from exc

        reader = PdfReader(file_path)
        pages_text: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())

        result = "\n\n".join(pages_text)
        logger.info("Parsed PDF %s: %d pages, %d chars", file_path, len(reader.pages), len(result))
        return result
