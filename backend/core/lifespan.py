"""FastAPI lifespan context manager."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, cleanup on shutdown."""
    from backend.core.service_container import ServiceContainer
    from backend.models.llm_loader import load_llm
    from backend.models.embedding_loader import load_embedder
    from backend.rag.memory_store import _get_collection

    container = ServiceContainer.get()

    # Load embedder (small, fast)
    try:
        container.embedder_model = load_embedder()
        logger.info("Embedder loaded.")
    except Exception as e:
        logger.error(f"Embedder load failed: {e}")

    # Load LLM (large, slow)
    try:
        container.llm_model, container.llm_tokenizer = load_llm()
        logger.info("LLM loaded.")
    except Exception as e:
        logger.error(f"LLM load failed: {e}")

    # Get Chroma collection
    try:
        container.chroma_collection = _get_collection()
        logger.info("Chroma collection ready.")
    except Exception as e:
        logger.error(f"Chroma init failed: {e}")

    # Try vLLM
    try:
        from backend.services.streaming_llm_service import try_init_vllm
        available, client = try_init_vllm()
        container.vllm_available = available
        container.vllm_client = client
        logger.info(f"vLLM available: {available}")
    except Exception as e:
        logger.info(f"vLLM not available: {e}")

    # Warmup pass
    if container.llm_model is not None and container.llm_tokenizer is not None:
        try:
            from backend.services.streaming_llm_service import stream_chat
            logger.info("Running warmup pass...")
            async for _ in stream_chat(
                messages=[{"role": "user", "content": "hi"}],
                max_new_tokens=4,
                temperature=0.0,
            ):
                pass
            container.warmed_up = True
            logger.info("Warmup complete.")
        except Exception as e:
            logger.warning(f"Warmup failed: {e}")

    yield

    # Cleanup
    if container.vllm_client is not None:
        try:
            await container.vllm_client.aclose()
        except Exception:
            pass
