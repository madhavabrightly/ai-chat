import logging
import os
from sentence_transformers import SentenceTransformer
from backend.config import EMBEDDING_MODEL_NAME, EMBEDDING_QUERY_INSTRUCTION
from backend.models.model_registry import get_model_path

logger = logging.getLogger(__name__)

embedder_model = None


def load_embedder():
    """Load the embedding model once from the registry active path."""
    global embedder_model

    try:
        model_path = get_model_path("embedding")
    except KeyError:
        model_path = None

    logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
    if model_path and os.path.isdir(model_path):
        logger.info(f"Loading from local path: {model_path}")
    else:
        logger.info(f"Loading from HuggingFace hub")
        from backend.config import MODEL_CACHE_DIR
        model_path = MODEL_CACHE_DIR

    embedder_model = SentenceTransformer(
        EMBEDDING_MODEL_NAME,
        cache_folder=model_path,
        trust_remote_code=True,
    )
    embedder_model.max_seq_length = 512
    embedder_model.default_prompt_name = "query"

    logger.info("Embedding model loaded successfully.")
    return embedder_model


def get_embedder():
    """Return the loaded embedder singleton."""
    if embedder_model is None:
        raise RuntimeError("Embedding model not loaded. Call load_embedder() first.")
    return embedder_model


def embed_query(text: str) -> list[float]:
    """Embed a single user query with the retrieval instruction prefix."""
    emb = get_embedder()
    query_text = f"{EMBEDDING_QUERY_INSTRUCTION}\n{text}"
    embedding = emb.encode(query_text, normalize_embeddings=True)
    return embedding.tolist()


def embed_documents(documents: list[str]) -> list[list[float]]:
    """Embed a list of document strings without the query instruction."""
    emb = get_embedder()
    embeddings = emb.encode(documents, normalize_embeddings=True)
    return [e.tolist() for e in embeddings]
