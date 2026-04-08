"""Milvus vector database client for BridgeAI."""
import logging

from pymilvus import DataType, MilvusClient

logger = logging.getLogger(__name__)

# Collection schemas
KNOWLEDGE_COLLECTION = "knowledge_chunk_vectors"
MEMORY_COLLECTION = "agent_memory_vectors"
EMBEDDING_DIM = 1024  # BGE-M3

_client: MilvusClient | None = None


def get_milvus_client() -> MilvusClient:
    global _client
    if _client is None:
        from app.config import settings

        uri = getattr(settings, "MILVUS_URI", "http://localhost:19530")
        token = getattr(settings, "MILVUS_TOKEN", "")
        _client = MilvusClient(uri=uri, token=token if token else None)
        _ensure_collections(_client)
    return _client


def _ensure_collections(client: MilvusClient) -> None:
    """Create collections if they don't exist."""
    # Knowledge chunks collection
    if not client.has_collection(KNOWLEDGE_COLLECTION):
        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("chunk_id", DataType.VARCHAR, max_length=36, is_primary=True)
        schema.add_field("knowledge_base_id", DataType.VARCHAR, max_length=36)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)

        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 256},
        )

        client.create_collection(
            collection_name=KNOWLEDGE_COLLECTION,
            schema=schema,
            index_params=index_params,
        )
        logger.info("Created Milvus collection: %s", KNOWLEDGE_COLLECTION)

    # Agent memory collection
    if not client.has_collection(MEMORY_COLLECTION):
        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("memory_id", DataType.VARCHAR, max_length=36, is_primary=True)
        schema.add_field("tenant_id", DataType.VARCHAR, max_length=36)
        schema.add_field("agent_id", DataType.VARCHAR, max_length=36)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)

        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 256},
        )

        client.create_collection(
            collection_name=MEMORY_COLLECTION,
            schema=schema,
            index_params=index_params,
        )
        logger.info("Created Milvus collection: %s", MEMORY_COLLECTION)


def close_milvus() -> None:
    global _client
    if _client:
        _client.close()
        _client = None
