"""
Memory Twin AI — Embedding Loader (Qwen3-Embedding-0.6B)

Upgraded with verified best practices from QwenLM/Qwen3-Embedding:
  - Uses the model's built-in "query" prompt (NO manual instruction prefix —
    the old code double-applied the instruction, hurting retrieval quality)
  - max_seq_length raised from 512 → 8192 (Qwen3-Embedding supports 32K)
  - Batch encoding with batch_size=32 for imported logs
  - normalize_embeddings=True (required for cosine similarity)

References:
  - QwenLM/Qwen3-Embedding README.md (L199-212) — Sentence Transformers usage
  - QwenLM/Qwen3-Embedding examples/qwen3_embedding_transformers.py (L14-56)
"""
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
    # Qwen3-Embedding supports up to 32K context; 8192 is the recommended default
    embedder_model.max_seq_length = 8192
    # Use the model's built-in query prompt (stored in model.prompts).
    # Do NOT also manually prepend EMBEDDING_QUERY_INSTRUCTION — that double-applies it.
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
    Embed a single user query.

    Uses the model's built-in "query" prompt (prompt_name="query") which
    applies the correct retrieval instruction internally. We do NOT manually
    prepend EMBEDDING_QUERY_INSTRUCTION — that would double-apply it.
    """
    emb = get_embedder()
    embedding = emb.encode(text, normalize_embeddings=True, prompt_name="query")
    return embedding.tolist()


def embed_documents(documents: list[str]) -> list[list[float]]:
    """
    Embed a list of document strings.

    Documents use NO query instruction (prompt_name=None) — only queries get
    the instruction prefix. Batched with batch_size=32 for throughput.
    """
    emb = get_embedder()
    embeddings = emb.encode(
        documents,
        normalize_embeddings=True,
        prompt_name=None,
        batch_size=32,
        show_progress_bar=len(documents) > 50,
        convert_to_numpy=True,
    )
    return [e.tolist() for e in embeddings]
