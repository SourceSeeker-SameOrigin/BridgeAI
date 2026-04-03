from abc import ABC, abstractmethod


class BaseParser(ABC):
    """Abstract base class for document parsers."""

    @abstractmethod
    def parse(self, file_path: str) -> str:
        """Parse the file at `file_path` and return extracted plain text."""
        ...

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this parser handles (e.g. ['.pdf'])."""
        ...
