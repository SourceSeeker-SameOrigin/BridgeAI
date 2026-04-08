"""Embedding providers for BridgeAI RAG and Memory."""
import logging
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 1024  # BGE-M3 output dimension


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts, returning a list of float vectors."""
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query text."""
        results = await self.embed_texts([text])
        return results[0]


class OllamaEmbedding(EmbeddingProvider):
    """Ollama local embedding using BGE-M3 (1024 dim, Chinese-optimized)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "bge-m3",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        # trust_env=False: Ollama is local, must bypass system/macOS proxy
        async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
            for text in texts:
                resp = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                resp.raise_for_status()
                results.append(resp.json()["embedding"])
        return results


class OpenAICompatEmbedding(EmbeddingProvider):
    """OpenAI-compatible embedding API (fallback)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "bge-m3",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"input": texts, "model": self.model},
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                item["embedding"]
                for item in sorted(data["data"], key=lambda x: x["index"])
            ]


def get_embedding_provider(model: str = "bge-m3") -> EmbeddingProvider:
    """Factory: returns Ollama (default) or OpenAI-compat provider."""
    from app.config import settings

    # Priority 1: Ollama (local, free)
    ollama_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
    if ollama_url:
        return OllamaEmbedding(base_url=ollama_url, model=model)

    # Priority 2: OpenAI-compatible API
    api_key = getattr(settings, "EMBEDDING_API_KEY", "")
    base_url = getattr(settings, "EMBEDDING_BASE_URL", "")
    if api_key and base_url:
        return OpenAICompatEmbedding(
            base_url=base_url, api_key=api_key, model=model
        )

    # Fallback: Ollama default
    return OllamaEmbedding(model=model)
