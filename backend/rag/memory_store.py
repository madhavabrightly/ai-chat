"""
Memory Twin AI — Vector Store (ChromaDB)

Upgraded with verified ChromaDB best practices from chroma-core/chroma:
  - Modern configuration={"hnsw":{...}} API (not deprecated metadata= form)
  - Tuned HNSW params: ef_construction=200, ef_search=100, max_neighbors=16
  - upsert (idempotent) instead of add (dup-risk on rebuild)
  - Collection metadata versioning (embedding model + dim + version)
  - Cosine space (correct for normalized Qwen3-Embedding vectors)

References:
  - chroma-core/chroma docs/mintlify/docs/collections/configure.mdx (L27-106)
  - chroma-core/chroma chromadb/segment/impl/vector/hnsw_params.py (L53-70)
"""
import json
import logging
import chromadb
from chromadb.config import Settings
from backend.config import MEMORIES_PATH, CHROMA_DB_DIR, EMBEDDING_MODEL_NAME, EMBEDDING_DIMENSION
from backend.models.embedding_loader import embed_query, embed_documents

logger = logging.getLogger(__name__)

_COLLECTION = None

# Tuned HNSW parameters (verified from ChromaDB docs)
_HNSW_CONFIG = {
    "space": "cosine",          # correct for normalized embeddings
    "ef_construction": 200,     # build-time search width (default 100; 200 = better graph)
    "ef_search": 100,           # query-time search width (default 10; 100 = better recall)
    "max_neighbors": 16,        # M — connections per node
}


def _get_collection():
    """Get or create the ChromaDB collection (singleton)."""
    global _COLLECTION
    if _COLLECTION is not None:
        return _COLLECTION

    logger.info(f"Initializing ChromaDB at: {CHROMA_DB_DIR}")
    client = chromadb.PersistentClient(
        path=CHROMA_DB_DIR,
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_or_create_collection(
        name="memory_twin",
        configuration={"hnsw": _HNSW_CONFIG},
        metadata={
            "embedding_model": EMBEDDING_MODEL_NAME,
            "embedding_dim": EMBEDDING_DIMENSION,
            "version": "v2",
            "description": "Memory Twin AI — personal memory store",
        },
    )
    _COLLECTION = collection
    return collection


def load_memories() -> list[dict]:
    """Read memories from the JSON file."""
    with open(MEMORIES_PATH, "r") as f:
        return json.load(f)


def build_vector_store() -> int:
    """
    Embed all memories and store them in ChromaDB.
    Uses upsert (idempotent) so rebuilds never create duplicates.
    Returns the number of memories indexed.
    """
    memories = load_memories()
    collection = _get_collection()

    # Check if already populated with the exact same IDs
    existing_ids = set(collection.get()["ids"]) if collection.count() > 0 else set()
    memory_ids = {m["memory_id"] for m in memories}
    if existing_ids == memory_ids:
        logger.info(f"Vector store already has {len(existing_ids)} memories — skipping rebuild.")
        return len(existing_ids)

    texts = [m["text"] for m in memories]
    logger.info(f"Embedding {len(texts)} memories...")
    embeddings = embed_documents(texts)

    ids = []
    documents = []
    metadatas_list = []

    for i, mem in enumerate(memories):
        mem_id = mem["memory_id"]
        ids.append(mem_id)
        documents.append(mem["text"])
        metadatas_list.append({
            "memory_id": mem_id,
            "title": mem.get("title", ""),
            "category": mem.get("category", ""),
            "emotion": mem.get("emotion", ""),
            "tags": ", ".join(mem.get("tags", [])),
        })

    # upsert is idempotent — safe to call on rebuild (add would error on dup IDs)
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas_list,
    )

    logger.info(f"Vector store built with {len(memories)} memories.")
    return len(memories)


def rebuild_vector_store() -> int:
    """Drop the existing collection and rebuild from scratch."""
    global _COLLECTION
    client = chromadb.PersistentClient(
        path=CHROMA_DB_DIR,
        settings=Settings(anonymized_telemetry=False),
    )
    try:
        client.delete_collection("memory_twin")
        logger.info("Deleted existing ChromaDB collection.")
    except ValueError:
        pass
    _COLLECTION = None
    return build_vector_store()


def get_all_memories() -> list[dict]:
    """Return all memories for the Memory Vault frontend."""
    return load_memories()
