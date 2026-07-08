import json
import logging
import chromadb
from chromadb.config import Settings
from backend.config import MEMORIES_PATH, CHROMA_DB_DIR
from backend.models.embedding_loader import embed_query, embed_documents

logger = logging.getLogger(__name__)

_COLLECTION = None


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
        metadata={"hnsw:space": "cosine"},
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
    Returns the number of memories indexed.
    """
    memories = load_memories()
    collection = _get_collection()

    # Check if already populated with distinct IDs
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

    collection.add(
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
