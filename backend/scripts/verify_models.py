"""
Memory Twin AI — Verify Models Script
Checks that both pre-trained models are available and can be loaded.

Usage:
    python -m backend.scripts.verify_models
"""
import logging
import os
import sys

_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _proj not in sys.path:
    sys.path.insert(0, _proj)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify_embedder():
    """Verify the embedding model loads and can embed text."""
    from backend.models.embedding_loader import load_embedder, embed_query

    logger.info("Verifying embedding model...")
    load_embedder()
    test_embedding = embed_query("What advice would you give me?")
    assert len(test_embedding) > 0, "Embedding should not be empty"
    logger.info(f"Embedding model OK. Embedding dim: {len(test_embedding)}")


def verify_llm():
    """Verify the LLM loads and can generate a short response."""
    from backend.models.llm_loader import load_llm, generate_answer

    logger.info("Verifying LLM...")
    load_llm()
    test_answer = generate_answer(
        system_prompt="You are a helpful assistant. Answer briefly.",
        user_prompt="Say 'Hello from Memory Twin AI' and nothing else.",
    )
    logger.info(f"LLM response: {test_answer[:100]}")
    logger.info("LLM OK.")


def verify_chromadb():
    """Verify ChromaDB can store and retrieve."""
    import chromadb
    from chromadb.config import Settings
    from backend.config import CHROMA_DB_DIR

    logger.info("Verifying ChromaDB...")
    client = chromadb.PersistentClient(
        path=CHROMA_DB_DIR,
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_or_create_collection(name="verify_test")
    collection.add(ids=["test_1"], documents=["This is a test memory."])
    results = collection.query(query_texts=["test"], n_results=1)
    assert len(results["ids"][0]) > 0, "Should find the test document"
    client.delete_collection("verify_test")
    logger.info("ChromaDB OK.")


if __name__ == "__main__":
    logger.info("=" * 46)
    logger.info("Memory Twin AI — Model & System Verification")
    logger.info("=" * 46)
    verify_embedder()
    verify_llm()
    verify_chromadb()
    logger.info("All systems verified. Ready to run.")
