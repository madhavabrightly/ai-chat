import logging
from backend.config import TOP_K
from backend.models.embedding_loader import embed_query
from backend.rag.memory_store import _get_collection

logger = logging.getLogger(__name__)


def retrieve_memories(question: str) -> list[dict]:
    """
    Embed the user question and query ChromaDB for the top-K relevant memories.

    Returns a list of dicts with:
        memory_id, title, category, emotion, snippet, full_text, relevance_score.
    """
    collection = _get_collection()

    logger.info(f"Retrieving memories for question: {question[:80]}...")
    query_embedding = embed_query(question)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K,
        include=["documents", "metadatas", "distances"],
    )

    retrieved = []
    if results["ids"] and results["ids"][0]:
        for i, mem_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            doc = results["documents"][0][i]
            distance = results["distances"][0][i] if results["distances"] else None

            retrieved.append({
                "memory_id": mem_id,
                "title": meta.get("title", ""),
                "category": meta.get("category", ""),
                "emotion": meta.get("emotion", ""),
                "snippet": doc[:200] + ("..." if len(doc) > 200 else ""),
                "full_text": doc,
                "relevance_score": round(1.0 - distance, 4) if distance else None,
            })

    logger.info(f"Retrieved {len(retrieved)} memories.")
    return retrieved
