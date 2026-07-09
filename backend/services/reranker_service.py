"""
Memory Twin AI — Reranker Service

Uses Qwen3-Reranker-0.6B to re-score retrieved memories for exactness.
Falls back gracefully if model is unavailable.
"""
import logging
import time
import torch
from backend.config import ENABLE_RERANKER
from backend.models.model_registry import model_exists_locally

logger = logging.getLogger(__name__)

reranker_model = None
reranker_tokenizer = None


def load_reranker():
    """Load reranker model if available."""
    global reranker_model, reranker_tokenizer
    if not ENABLE_RERANKER:
        logger.info("Reranker disabled (ENABLE_RERANKER=false).")
        return None
    if not model_exists_locally("reranker"):
        logger.info("Reranker model not found locally. Using embedding-only retrieval.")
        return None
    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        from backend.models.model_registry import get_model_path
        path = get_model_path("reranker")
        logger.info(f"Loading reranker from: {path}")
        reranker_tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
        reranker_model = AutoModelForSequenceClassification.from_pretrained(
            path, torch_dtype="auto", device_map="auto", trust_remote_code=True
        )
        logger.info("Reranker loaded successfully.")
        return reranker_model
    except Exception as e:
        logger.warning(f"Reranker load failed: {e}. Using embedding-only retrieval.")
        reranker_model = None
        return None


def rerank(query: str, documents: list[dict]) -> list[dict]:
    """
    Re-rank documents by relevance to the query.
    Falls back to original scores if reranker unavailable.
    Returns documents sorted by relevance.
    """
    if reranker_model is None or reranker_tokenizer is None:
        return documents

    try:
        pairs = [(query, d.get("full_text", d.get("text", ""))) for d in documents]
        inputs = reranker_tokenizer(
            pairs, padding=True, truncation=True, return_tensors="pt", max_length=512
        ).to(reranker_model.device)

        with torch.no_grad():
            scores = reranker_model(**inputs).logits.squeeze(-1).cpu().tolist()

        if not isinstance(scores, list):
            scores = [scores]

        for i, doc in enumerate(documents):
            if i < len(scores):
                doc["relevance_score"] = round(float(scores[i]), 4)

        documents.sort(key=lambda d: d.get("relevance_score", 0), reverse=True)
        return documents
    except Exception as e:
        logger.warning(f"Reranker inference failed: {e}")
        return documents
