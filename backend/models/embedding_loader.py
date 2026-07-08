import logging
import os
from sentence_transformers import SentenceTransformer
from backend.config import EMBEDDING_MODEL_NAME, EMBEDDING_QUERY_INSTRUCTION, MODEL_CACHE_DIR

logger = logging.getLogger(__name__)

# Global singleton — loaded once at startup, never per request
embedder_model = None


def load_embedder():
    """Load the embedding model once and cache it globally."""
    global embedder_model

    cache_path = os.path.join(MODEL_CACHE_DIR, EMBEDDING_MODEL_NAME.replace("/", "_"))

    logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
    logger.info(f"Model cache path: {cache_path}")

    embedder_model = SentenceTransformer(
        EMBEDDING_MODEL_NAME,
        cache_folder=cache_path,
        trust_remote_code=True,
    )
    embedder_model.max_seq_length = 512  # Qwen3-Embedding-0.6B safe ceiling

    # SentenceTransformer v3+ for Qwen3-Embedding uses modern pipeline
    embedder_model.default_prompt_name = "query"

    logger.info("Embedding model loaded successfully.")
    return embedder_model


def get_embedder():
    """Return the loaded embedder singleton."""
    if embedder_model is None:
        raise RuntimeError("Embedding model not loaded. Call load_embedder() first.")
    return embedder_model


def embed_query(text: str) -> list[float]:
    """
    Embed a single user query with the retrieval instruction prefix.
    Normalizes the embedding for cosine similarity.
    """
    emb = get_embedder()
    query_text = f"{EMBEDDING_QUERY_INSTRUCTION}\n{text}"
    embedding = emb.encode(query_text, normalize_embeddings=True)
    return embedding.tolist()


def embed_documents(documents: list[str]) -> list[list[float]]:
    """
    Embed a list of document strings (memories) without the query instruction.
    Normalizes embeddings for cosine similarity.
    """
    emb = get_embedder()
    embeddings = emb.encode(documents, normalize_embeddings=True)
    return [e.tolist() for e in embeddings]
