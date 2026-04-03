import os

from app.rag.parsers.base import BaseParser
from app.rag.parsers.docx_parser import DocxParser
from app.rag.parsers.excel_parser import ExcelParser
from app.rag.parsers.markdown_parser import MarkdownParser
from app.rag.parsers.pdf_parser import PdfParser
from app.rag.parsers.text_parser import TextParser

# Build extension → parser mapping
_PARSERS: list[BaseParser] = [
    PdfParser(),
    DocxParser(),
    ExcelParser(),
    MarkdownParser(),
    TextParser(),
]

_EXTENSION_MAP: dict[str, BaseParser] = {}
for parser in _PARSERS:
    for ext in parser.supported_extensions:
        _EXTENSION_MAP[ext.lower()] = parser


def get_parser(filename: str) -> BaseParser:
    """Select and return the appropriate parser based on file extension.

    Falls back to TextParser for unknown extensions.
    """
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext in _EXTENSION_MAP:
        return _EXTENSION_MAP[ext]
    # Fallback to plain text parser for unknown extensions
    return TextParser()
