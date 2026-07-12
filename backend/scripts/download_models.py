"""
Memory Twin AI — Download Models Script
Downloads both pre-trained models from ModelScope / HuggingFace.
Models are cached outside the git repo (default: /workspace/memory_twin_models).

Usage:
    python -m backend.scripts.download_models
"""
import logging
import os
import sys

# Ensure backend package is importable
_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _proj not in sys.path:
    sys.path.insert(0, _proj)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def download_llm():
    """Download Qwen/Qwen2.5-7B-Instruct using transformers."""
    from backend.config import LLM_MODEL_NAME, MODEL_CACHE_DIR
    from transformers import AutoModelForCausalLM, AutoTokenizer

    cache_path = os.path.join(MODEL_CACHE_DIR, LLM_MODEL_NAME.replace("/", "_"))
    logger.info(f"Downloading LLM: {LLM_MODEL_NAME}")
    logger.info(f"Cache path: {cache_path}")

    logger.info("Downloading tokenizer...")
    AutoTokenizer.from_pretrained(LLM_MODEL_NAME, cache_dir=cache_path, trust_remote_code=True)

    logger.info("Downloading model (this may take a while ~4 GB)...")
    AutoModelForCausalLM.from_pretrained(
        LLM_MODEL_NAME,
        cache_dir=cache_path,
        torch_dtype="auto",
        trust_remote_code=True,
    )
    logger.info("LLM downloaded successfully.")


def download_embedder():
    """Download Qwen/Qwen3-Embedding-0.6B using SentenceTransformer."""
    from backend.config import EMBEDDING_MODEL_NAME, MODEL_CACHE_DIR
    from sentence_transformers import SentenceTransformer

    cache_path = os.path.join(MODEL_CACHE_DIR, EMBEDDING_MODEL_NAME.replace("/", "_"))
    logger.info(f"Downloading embedding model: {EMBEDDING_MODEL_NAME}")
    logger.info(f"Cache path: {cache_path}")

    SentenceTransformer(
        EMBEDDING_MODEL_NAME,
        cache_folder=cache_path,
        trust_remote_code=True,
    )
    logger.info("Embedding model downloaded successfully.")


if __name__ == "__main__":
    logger.info("=" * 46)
    logger.info("Memory Twin AI — Model Downloader")
    logger.info("=" * 46)
    download_embedder()
    download_llm()
    logger.info("All models downloaded. Ready to run the backend.")
