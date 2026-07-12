"""Singleton service container — holds all backend services."""
import logging
import threading
from typing import Any, Optional

from backend.core.lru_cache import LRUCache

logger = logging.getLogger(__name__)


class ServiceContainer:
    """Singleton holder for all backend services (LLM, embedder, Chroma, caches)."""

    _instance: Optional["ServiceContainer"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.llm_model = None
        self.llm_tokenizer = None
        self.embedder_model = None
        self.chroma_collection = None
        self.vllm_client = None
        self.vllm_available = False
        self.avatar_action_model = None
        self.avatar_action_tokenizer = None
        self.warmed_up = False
        self.memory_version = 0

        # Caches
        self.embedding_cache = LRUCache(max_size=512, ttl_seconds=600.0)
        self.retrieval_cache = LRUCache(max_size=256, ttl_seconds=120.0)
        self.app_answer_cache = LRUCache(max_size=128, ttl_seconds=300.0)

    @classmethod
    def get(cls) -> "ServiceContainer":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    def bump_memory_version(self) -> None:
        """Invalidate retrieval cache when memories change."""
        self.memory_version += 1
        invalidated = self.retrieval_cache.invalidate("ret:")
        logger.info(f"Memory version bumped to {self.memory_version}, invalidated {invalidated} retrieval cache entries")

    def all_stats(self) -> dict:
        return {
            "warmed_up": self.warmed_up,
            "vllm_available": self.vllm_available,
            "memory_version": self.memory_version,
            "embedding_cache": self.embedding_cache.stats(),
            "retrieval_cache": self.retrieval_cache.stats(),
            "app_answer_cache": self.app_answer_cache.stats(),
        }
