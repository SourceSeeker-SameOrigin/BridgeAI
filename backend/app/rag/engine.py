"""RAG engine: parse, chunk, embed (Ollama BGE-M3), store vectors in Milvus."""
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from app.rag.chunker import split_text
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.milvus_client import KNOWLEDGE_COLLECTION, get_milvus_client
from app.rag.parsers import get_parser

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    """A single search result from the knowledge base."""

    chunk_id: str
    content: str
    similarity: float
    chunk_index: int
    document_id: str


class RAGEngine:
    """Main RAG orchestrator: parse, chunk, embed, store, and search."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._embedding_providers: dict[str, EmbeddingProvider] = {}

    def _get_embedding_provider(self, model: str) -> EmbeddingProvider:
        if model not in self._embedding_providers:
            self._embedding_providers[model] = get_embedding_provider(model)
        return self._embedding_providers[model]

    async def ingest_document(
        self,
        knowledge_base_id: str,
        file_path: str,
        filename: str,
        document_id: str,
    ) -> str:
        """Parse -> Chunk -> Embed via Ollama -> Store vectors in Milvus + metadata in PostgreSQL.

        Returns the document_id on success.
        """
        try:
            # Update status to processing
            await self._update_document_status(document_id, "processing")

            # 1. Get knowledge base config
            result = await self._db.execute(
                select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
            )
            kb = result.scalar_one_or_none()
            if kb is None:
                raise ValueError(f"Knowledge base {knowledge_base_id} not found")

            # 2. Parse document
            parser = get_parser(filename)
            text_content = parser.parse(file_path)
            if not text_content.strip():
                await self._update_document_status(document_id, "ready", chunk_count=0)
                await self._db.commit()
                return document_id

            # 3. Chunk text
            chunks = split_text(
                text_content,
                chunk_size=kb.chunk_size,
                chunk_overlap=kb.chunk_overlap,
            )
            if not chunks:
                await self._update_document_status(document_id, "ready", chunk_count=0)
                await self._db.commit()
                return document_id

            # 4. Embed chunks via Ollama BGE-M3
            embedder = self._get_embedding_provider(kb.embedding_model)
            chunk_texts = [c.content for c in chunks]

            batch_size = 100
            all_embeddings: list[list[float]] = []
            for i in range(0, len(chunk_texts), batch_size):
                batch = chunk_texts[i : i + batch_size]
                batch_embeddings = await embedder.embed_texts(batch)
                all_embeddings.extend(batch_embeddings)

            # 5. Store: vectors in Milvus + metadata in PostgreSQL
            milvus = get_milvus_client()
            milvus_rows: list[dict] = []

            for chunk, embedding in zip(chunks, all_embeddings):
                chunk_id = str(uuid.uuid4())

                # Insert metadata into PostgreSQL (no embedding column)
                await self._db.execute(
                    text(
                        """
                        INSERT INTO knowledge_chunks
                            (id, document_id, knowledge_base_id, tenant_id, content,
                             chunk_index, token_count, metadata, created_at, updated_at)
                        VALUES
                            (:id, :document_id, :knowledge_base_id, :tenant_id, :content,
                             :chunk_index, :token_count, :metadata, NOW(), NOW())
                        """
                    ),
                    {
                        "id": chunk_id,
                        "document_id": document_id,
                        "knowledge_base_id": knowledge_base_id,
                        "tenant_id": str(kb.tenant_id),
                        "content": chunk.content,
                        "chunk_index": chunk.index,
                        "token_count": len(chunk.content),
                        "metadata": "{}",
                    },
                )

                # Collect for Milvus batch insert
                milvus_rows.append(
                    {
                        "chunk_id": chunk_id,
                        "knowledge_base_id": knowledge_base_id,
                        "embedding": embedding,
                    }
                )

            # Batch insert vectors into Milvus
            if milvus_rows:
                milvus.insert(
                    collection_name=KNOWLEDGE_COLLECTION,
                    data=milvus_rows,
                )

            # 6. Update document status
            await self._update_document_status(
                document_id, "ready", chunk_count=len(chunks)
            )
            await self._db.commit()
            logger.info(
                "Ingested document %s: %d chunks stored", document_id, len(chunks)
            )
            return document_id

        except Exception as exc:
            logger.exception("Failed to ingest document %s", document_id)
            try:
                await self._db.rollback()
                await self._update_document_status(
                    document_id, "error", error_message=str(exc)
                )
                await self._db.commit()
            except Exception:
                logger.exception("Failed to update document error status")
            raise

    async def search(
        self,
        knowledge_base_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Embed query via Ollama -> Milvus vector search -> PostgreSQL for content."""
        # Get knowledge base to determine embedding model
        result = await self._db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
        )
        kb = result.scalar_one_or_none()
        if kb is None:
            raise ValueError(f"Knowledge base {knowledge_base_id} not found")

        # Embed query
        embedder = self._get_embedding_provider(kb.embedding_model)
        query_embedding = await embedder.embed_query(query)

        # Search in Milvus with knowledge_base_id filter
        milvus = get_milvus_client()
        milvus_results = milvus.search(
            collection_name=KNOWLEDGE_COLLECTION,
            data=[query_embedding],
            filter=f'knowledge_base_id == "{knowledge_base_id}"',
            limit=top_k,
            output_fields=["chunk_id"],
        )

        if not milvus_results or not milvus_results[0]:
            return []

        # Extract chunk_ids and scores
        chunk_scores: dict[str, float] = {}
        for hit in milvus_results[0]:
            chunk_id = hit["entity"]["chunk_id"]
            # Milvus COSINE returns distance; similarity = 1 - distance for IP,
            # but for COSINE metric_type the score IS the cosine similarity
            chunk_scores[chunk_id] = float(hit["distance"])

        if not chunk_scores:
            return []

        # Query PostgreSQL for chunk content
        chunk_ids = list(chunk_scores.keys())
        rows = await self._db.execute(
            text(
                """
                SELECT id, content, document_id, chunk_index
                FROM knowledge_chunks
                WHERE id = ANY(:ids)
                """
            ),
            {"ids": chunk_ids},
        )

        results: list[SearchResult] = []
        for row in rows:
            cid = str(row.id)
            results.append(
                SearchResult(
                    chunk_id=cid,
                    content=row.content,
                    similarity=chunk_scores.get(cid, 0.0),
                    chunk_index=row.chunk_index,
                    document_id=str(row.document_id),
                )
            )

        # Sort by similarity descending
        results.sort(key=lambda r: r.similarity, reverse=True)
        return results

    async def delete_document(self, document_id: str) -> None:
        """Delete a document: remove vectors from Milvus + metadata from PostgreSQL."""
        # Get chunk IDs for this document
        rows = await self._db.execute(
            text("SELECT id FROM knowledge_chunks WHERE document_id = :doc_id"),
            {"doc_id": document_id},
        )
        chunk_ids = [str(row.id) for row in rows]

        # Delete from Milvus
        if chunk_ids:
            milvus = get_milvus_client()
            id_filter = " || ".join(
                [f'chunk_id == "{cid}"' for cid in chunk_ids]
            )
            milvus.delete(
                collection_name=KNOWLEDGE_COLLECTION,
                filter=id_filter,
            )

        # Delete from PostgreSQL
        await self._db.execute(
            text("DELETE FROM knowledge_chunks WHERE document_id = :doc_id"),
            {"doc_id": document_id},
        )
        await self._db.execute(
            text("DELETE FROM knowledge_documents WHERE id = :doc_id"),
            {"doc_id": document_id},
        )
        await self._db.commit()
        logger.info("Deleted document %s and its chunks", document_id)

    async def _update_document_status(
        self,
        document_id: str,
        status: str,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        values: dict = {"status": status}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        if error_message is not None:
            values["error_message"] = error_message

        await self._db.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .values(**values)
        )
