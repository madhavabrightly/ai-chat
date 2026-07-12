"""
Memory Twin AI — Temporal Retriever (Phase 2)

Implements the Memory Truth Contract retrieval pipeline:

  1. Fetch top 20 candidates via dense (Qwen3-Embedding-0.6B) + sparse (BM25)
     + Reciprocal Rank Fusion
  2. Apply optional date-range filter (for TEMPORAL_COMPARISON questions)
  3. Rerank with bge-reranker-v2-m3 (or Qwen3-Reranker fallback) → top 5
  4. Return evidence chunks with full metadata for source cards

This module is the bridge between the question classifier and the answer
generator. It enforces the "top 20 → top 5" pipeline required by the
Memory Truth Contract.
"""
import logging
from backend.config import TOP_K
from backend.models.embedding_loader import embed_query
from backend.rag.memory_store import _get_collection, load_memories
from backend.rag.query_transform import reciprocal_rank_fusion
from backend.rag.question_classifier import (
    TEMPORAL_COMPARISON,
    needs_date_filter,
)

logger = logging.getLogger(__name__)

# Pipeline constants (per Memory Truth Contract)
FETCH_K = 20   # over-fetch: retrieve 20 candidates
RERANK_K = 5   # final: return top 5 after reranking

# BM25 index (built lazily)
_BM25_INDEX = None
_BM25_DOCS = None


def _build_bm25_index():
    """Build a BM25 index over all memory texts (call once, lazily)."""
    global _BM25_INDEX, _BM25_DOCS
    try:
        from rank_bm25 import BM25Okapi
        memories = load_memories()
        _BM25_DOCS = memories
        tokenized = [m["text"].lower().split() for m in memories]
        _BM25_INDEX = BM25Okapi(tokenized)
        logger.info(f"BM25 index built with {len(memories)} memories.")
    except ImportError:
        logger.info("rank_bm25 not installed — hybrid search disabled (dense-only).")
        _BM25_INDEX = None
    except Exception as e:
        logger.warning(f"BM25 index build failed: {e}")
        _BM25_INDEX = None


def _bm25_search(question: str, k: int = 20) -> list[dict]:
    """Sparse BM25 search. Returns list of {memory_id, bm25_score}."""
    if _BM25_INDEX is None:
        _build_bm25_index()
    if _BM25_INDEX is None or _BM25_DOCS is None:
        return []
    try:
        scores = _BM25_INDEX.get_scores(question.lower().split())
        top_idx = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        return [
            {"memory_id": _BM25_DOCS[i]["memory_id"], "bm25_score": float(scores[i])}
            for i in top_idx if scores[i] > 0
        ]
    except Exception as e:
        logger.warning(f"BM25 search failed: {e}")
        return []


def _dense_search(question: str, n_results: int = 20, where: dict = None) -> list[dict]:
    """Dense vector search via ChromaDB."""
    collection = _get_collection()
    query_embedding = embed_query(question)

    query_kwargs = dict(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    if where:
        query_kwargs["where"] = where

    results = collection.query(**query_kwargs)

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
                "relevance_score": round(1.0 - distance, 4) if distance is not None else None,
            })
    return retrieved


def _apply_date_filter(candidates: list[dict], date_from: str = None, date_to: str = None) -> list[dict]:
    """
    Filter candidates by date range (for TEMPORAL_COMPARISON questions).
    date_from / date_to are ISO 8601 strings. Inclusive on both ends.

    Handles both full ISO timestamps (2026-01-18T23:59:59) and date-only
    strings (2026-01-18) by normalizing to a comparable form.
    """
    if not date_from and not date_to:
        return candidates

    # Normalize bounds: if date_from is date-only, treat as start of day
    # if date_to is date-only, treat as end of day for inclusive comparison
    norm_from = date_from if "T" in (date_from or "") else f"{date_from}T00:00:00" if date_from else None
    norm_to = date_to if "T" in (date_to or "") else f"{date_to}T23:59:59" if date_to else None

    filtered = []
    for c in candidates:
        ts = c.get("timestamp_iso", "") or c.get("date", "")
        if not ts:
            continue
        # Normalize candidate timestamp for comparison
        cand_ts = ts if "T" in ts else f"{ts}T00:00:00" if len(ts) == 10 else ts
        if norm_from and cand_ts < norm_from:
            continue
        if norm_to and cand_ts > norm_to:
            continue
        filtered.append(c)
    return filtered


def retrieve_top20(
    question: str,
    history: list[dict] = None,
    where: dict = None,
    use_hybrid: bool = True,
    date_from: str = None,
    date_to: str = None,
) -> list[dict]:
    """
    Retrieve top 20 candidates for a question.

    Pipeline:
      1. Condense follow-up questions into standalone queries (if history given)
      2. Dense search (ChromaDB) + sparse search (BM25)
      3. Reciprocal Rank Fusion to merge rankings
      4. Optional date-range filter (for TEMPORAL_COMPARISON)
      5. Return top 20 candidates

    Args:
      question: the user's question
      history: optional chat history for condense-then-retrieve
      where: optional ChromaDB metadata filter
      use_hybrid: enable BM25+dense fusion (default True)
      date_from: ISO 8601 lower bound (inclusive)
      date_to: ISO 8601 upper bound (inclusive)
    """
    # Step 1: condense follow-up into standalone query
    effective_query = question
    if history:
        try:
            from backend.rag.query_transform import condense_question
            effective_query = condense_question(question, history)
            if effective_query != question:
                logger.info(f"Condensed query: '{question[:40]}' → '{effective_query[:40]}'")
        except Exception as e:
            logger.debug(f"condense skipped: {e}")

    # Step 2: dense search (fetch 20)
    dense = _dense_search(effective_query, n_results=FETCH_K, where=where)
    logger.info(f"Dense search: {len(dense)} candidates for: {effective_query[:80]}...")

    if not use_hybrid:
        merged = dense
    else:
        # Step 3: sparse (BM25) search
        sparse = _bm25_search(effective_query, k=FETCH_K)
        if not sparse:
            merged = dense
        else:
            # Reciprocal Rank Fusion
            dense_ids = [d["memory_id"] for d in dense]
            sparse_ids = [s["memory_id"] for s in sparse]
            fused = reciprocal_rank_fusion([dense_ids, sparse_ids])

            # Re-attach full doc data
            by_id = {d["memory_id"]: d for d in dense}
            if _BM25_DOCS:
                for m in _BM25_DOCS:
                    if m["memory_id"] not in by_id:
                        by_id[m["memory_id"]] = {
                            "memory_id": m["memory_id"],
                            "title": m.get("title", ""),
                            "category": m.get("category", ""),
                            "emotion": m.get("emotion", ""),
                            "snippet": m["text"][:200] + ("..." if len(m["text"]) > 200 else ""),
                            "full_text": m["text"],
                            "relevance_score": None,
                        }

            merged = []
            for doc_id, fused_score in fused:
                doc = by_id.get(doc_id)
                if doc:
                    doc["fused_score"] = round(fused_score, 4)
                    merged.append(doc)

    # Step 4: date filter (for TEMPORAL_COMPARISON)
    if date_from or date_to:
        before = len(merged)
        merged = _apply_date_filter(merged, date_from, date_to)
        logger.info(f"Date filter [{date_from} → {date_to}]: {before} → {len(merged)}")

    logger.info(f"Top-{FETCH_K} retrieval: {len(merged)} candidates")
    return merged[:FETCH_K]


def retrieve_top5_with_rerank(
    question: str,
    history: list[dict] = None,
    where: dict = None,
    use_hybrid: bool = True,
    date_from: str = None,
    date_to: str = None,
    reranker=None,
    min_score: float = 0.0,
) -> list[dict]:
    """
    Full Memory Truth Contract pipeline:
      1. Retrieve top 20 candidates
      2. Rerank with bge-reranker-v2-m3 (or fallback) → top 5

    Args:
      question: the user's question
      history: optional chat history
      where: optional ChromaDB metadata filter
      use_hybrid: enable BM25+dense fusion
      date_from: ISO 8601 lower bound
      date_to: ISO 8601 upper bound
      reranker: optional rerank function (defaults to backend.services.reranker_service.rerank)
      min_score: minimum reranker score to keep a doc

    Returns:
      List of top 5 evidence chunks with full metadata.
    """
    # Step 1: retrieve top 20
    candidates = retrieve_top20(
        question=question,
        history=history,
        where=where,
        use_hybrid=use_hybrid,
        date_from=date_from,
        date_to=date_to,
    )

    if not candidates:
        return []

    # Step 2: rerank → top 5
    if reranker is None:
        try:
            from backend.services.reranker_service import rerank
            reranked = rerank(question, candidates, min_score=min_score)
        except Exception as e:
            logger.warning(f"Reranker unavailable, using dense order: {e}")
            reranked = candidates
    else:
        try:
            reranked = reranker(question, candidates, min_score=min_score)
        except Exception as e:
            logger.warning(f"Custom reranker failed: {e}")
            reranked = candidates

    # Take top 5
    top5 = reranked[:RERANK_K]
    logger.info(f"Final top-{RERANK_K}: {len(top5)} evidence chunks")
    return top5
