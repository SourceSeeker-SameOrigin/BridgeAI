import logging
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# Target embedding dimension — must match pgvector column vector(1536)
EMBEDDING_DIM = 1536


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts, returning a list of float vectors."""
        ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query text."""
        ...


class OpenAICompatibleEmbedding(EmbeddingProvider):
    """Embedding via OpenAI-compatible API (works with OpenAI, DeepSeek, Qwen, etc.)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "text-embedding-3-small",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        import httpx

        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"input": texts, "model": self.model}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        embeddings = [item["embedding"] for item in data["data"]]
        # Pad or truncate to EMBEDDING_DIM
        return [_normalize_dim(emb) for emb in embeddings]

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed_texts([text])
        return results[0]


class TfidfLocalEmbedding(EmbeddingProvider):
    """Local hash-based embedding for development/testing — no API key needed.

    Uses scikit-learn HashingVectorizer with character n-grams. Unlike
    TfidfVectorizer, HashingVectorizer is STATELESS — it does not need to be
    fitted on a corpus first. This means ingestion and search can run in
    separate processes without sharing any state, and the same text always
    produces the same vector.

    The resulting vectors are padded or truncated to EMBEDDING_DIM (1536) to
    match the pgvector column size.
    """

    def __init__(self) -> None:
        self._vectorizer: Optional[object] = None

    def _get_vectorizer(self) -> object:
        if self._vectorizer is None:
            from sklearn.feature_extraction.text import HashingVectorizer

            self._vectorizer = HashingVectorizer(
                n_features=EMBEDDING_DIM,
                analyzer="char_wb",
                ngram_range=(2, 4),
                alternate_sign=False,
                norm="l2",
            )
        return self._vectorizer

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectorizer = self._get_vectorizer()
        matrix = vectorizer.transform(texts)  # type: ignore[union-attr]
        results: list[list[float]] = []
        for i in range(matrix.shape[0]):
            row = matrix.getrow(i).toarray().flatten()
            results.append(_normalize_dim(row.tolist()))
        return results

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed_texts([text])
        return results[0]


def _normalize_dim(vector: list[float]) -> list[float]:
    """Pad or truncate vector to EMBEDDING_DIM, then L2-normalize."""
    arr = np.array(vector, dtype=np.float64)
    if len(arr) < EMBEDDING_DIM:
        arr = np.pad(arr, (0, EMBEDDING_DIM - len(arr)), mode="constant")
    elif len(arr) > EMBEDDING_DIM:
        arr = arr[:EMBEDDING_DIM]
    # L2 normalize
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr.tolist()


def get_embedding_provider(model: str = "text-embedding-3-small") -> EmbeddingProvider:
    """Factory: return an embedding provider based on available configuration.

    Tries API-based providers first; falls back to local TF-IDF.
    """
    # Check for configured API keys
    embedding_api_key = getattr(settings, "EMBEDDING_API_KEY", None)
    embedding_base_url = getattr(settings, "EMBEDDING_BASE_URL", None)

    if embedding_api_key:
        base_url = embedding_base_url or "https://api.openai.com/v1"
        logger.info("Using OpenAI-compatible embedding: model=%s, base_url=%s", model, base_url)
        return OpenAICompatibleEmbedding(
            api_key=embedding_api_key,
            base_url=base_url,
            model=model,
        )

    # Fallback to local TF-IDF
    logger.info("No EMBEDDING_API_KEY configured, using local TF-IDF embedding (dev mode)")
    return TfidfLocalEmbedding()
