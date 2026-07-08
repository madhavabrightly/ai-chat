"""
Memory Twin AI — Model path constants and helpers.

Centralizes where models are stored on disk.
Models are NOT stored in the git repo — they live in:
  /workspace/memory_twin_models/  (primary)
  ./runtime_cache/models/         (fallback)
"""
import os
from .config import LLM_MODEL_NAME, EMBEDDING_MODEL_NAME, MODEL_CACHE_DIR


def llm_model_path() -> str:
    """Return the local filesystem path for the cached LLM."""
    return os.path.join(MODEL_CACHE_DIR, LLM_MODEL_NAME.replace("/", "_"))


def embedding_model_path() -> str:
    """Return the local filesystem path for the cached embedding model."""
    return os.path.join(MODEL_CACHE_DIR, EMBEDDING_MODEL_NAME.replace("/", "_"))


def model_cache_summary() -> str:
    """Return a human-readable summary of the model cache."""
    return f"Model cache directory: {MODEL_CACHE_DIR}"
