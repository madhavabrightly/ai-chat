"""
Memory Twin AI — Memory Retriever (Optimized)

Upgraded with state-of-the-art retrieval techniques:
  - Hybrid search: dense (ChromaDB) + sparse (BM25) fused via RRF
  - Query condensing for follow-up questions (LlamaIndex pattern)
  - Optional metadata filtering (category, emotion)
  - Over-fetch + rerank (retrieves TOP_K*3, lets reranker pick the best)
  - HyDE query expansion (optional, via query_transform)
  - LRU caching for query embeddings and retrieval results
  - Uses service container for singleton access (no per-request init)

References:
  - RAG-Fusion (Wang et al. 2024) — RRF
  - LlamaIndex chat_engine/condense_plus_context.py — condense pattern
  - rank_bm25 — BM25Okapi sparse retrieval
"""
import logging
import time
from backend.config import TOP_K, NORMAL_N_RESULTS, EXACT_N_RESULTS, ENABLE_QUERY_CACHE
from backend.core.service_container import ServiceContainer
from backend.rag.memory_store import _get_collection, load_memories
from backend.rag.query_transform import reciprocal_rank_fusion, condense_question

logger = logging.getLogger(__name__)

# BM25 index (built lazily on first hybrid search)
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


def _bm25_search(question: str, k: int = 10) -> list[dict]:
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


def _embed_query_cached(question: str) -> list[float]:
    """Embed query with LRU cache."""
    container = ServiceContainer.get()
    if not ENABLE_QUERY_CACHE:
        from backend.models.embedding_loader import embed_query
        return embed_query(question)

    key = f"emb:{question.strip().lower()}"
    cached = container.embedding_cache.get(key)
    if cached is not None:
        return cached

    from backend.models.embedding_loader import embed_query
    embedding = embed_query(question)
    container.embedding_cache.set(key, embedding)
    return embedding


def _dense_search(question: str, n_results: int, where: dict = None) -> list[dict]:
    """Dense vector search via ChromaDB (uses service container)."""
    container = ServiceContainer.get()
    collection = container.chroma_collection or _get_collection()
    query_embedding = _embed_query_cached(question)

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


def retrieve_memories(
    question: str,
    history: list[dict] = None,
    where: dict = None,
    use_hybrid: bool = True,
    over_fetch: int = None,
    n_results: int = None,
    use_cache: bool = True,
) -> list[dict]:
    """
    Retrieve the top-K relevant memories for a question.

    Pipeline:
      1. Condense follow-up questions into standalone queries (if history given)
      2. Dense search (ChromaDB) + sparse search (BM25)
      3. Reciprocal Rank Fusion to merge rankings
      4. Over-fetch (TOP_K*3) so the reranker has room to improve ordering

    Args:
      question: the user's question
      history: optional chat history for condense-then-retrieve
      where: optional ChromaDB metadata filter, e.g. {"category": "Career"}
      use_hybrid: enable BM25+dense fusion (default True)
      over_fetch: how many candidates to retrieve before reranking (default TOP_K*3)
      n_results: explicit number of results (overrides over_fetch)
      use_cache: whether to use LRU cache for retrieval results
    """
    container = ServiceContainer.get()

    # Step 1: condense follow-up into standalone query
    effective_query = question
    if history:
        try:
            effective_query = condense_question(question, history)
            if effective_query != question:
                logger.debug(f"Condensed query: '{question[:40]}' → '{effective_query[:40]}'")
        except Exception as e:
            logger.debug(f"condense skipped: {e}")

    # Check cache
    cache_key = None
    if use_cache and ENABLE_QUERY_CACHE:
        cache_key = f"ret:{effective_query.strip().lower()}:v{container.memory_version}:n{n_results or over_fetch or (TOP_K*3)}:w{where}"
        cached = container.retrieval_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Retrieval cache hit for: {effective_query[:40]}")
            return cached

    fetch_n = n_results or over_fetch or (TOP_K * 3)

    # Step 2: dense search
    t_dense = time.time()
    dense = _dense_search(effective_query, n_results=fetch_n, where=where)
    dense_ms = (time.time() - t_dense) * 1000
    logger.debug(f"Dense search: {len(dense)} candidates in {dense_ms:.1f}ms")

    if not use_hybrid:
        result = dense[:TOP_K]
        if cache_key:
            container.retrieval_cache.set(cache_key, result)
        return result

    # Step 3: sparse (BM25) search
    t_sparse = time.time()
    sparse = _bm25_search(effective_query, k=fetch_n)
    sparse_ms = (time.time() - t_sparse) * 1000
    logger.debug(f"BM25 search: {len(sparse)} candidates in {sparse_ms:.1f}ms")

    if not sparse:
        # BM25 unavailable or empty — dense-only
        result = dense[:TOP_K]
        if cache_key:
            container.retrieval_cache.set(cache_key, result)
        return result

    # Step 4: Reciprocal Rank Fusion of dense + sparse rankings
    dense_ids = [d["memory_id"] for d in dense]
    sparse_ids = [s["memory_id"] for s in sparse]
    fused = reciprocal_rank_fusion([dense_ids, sparse_ids])

    # Re-attach full doc data from dense results (BM25 only returns IDs+scores)
    by_id = {d["memory_id"]: d for d in dense}
    # Also pull from BM25 docs for items not in dense results
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

    result = merged[:fetch_n]
    if cache_key:
        container.retrieval_cache.set(cache_key, result)
    logger.debug(f"Hybrid retrieval: {len(result)} fused candidates (dense={dense_ms:.1f}ms, sparse={sparse_ms:.1f}ms)")
    return result


# Backward-compatible alias
def retrieve_top5_with_rerank(question: str, history: list = None, use_hybrid: bool = True) -> list[dict]:
    """Legacy interface — returns top-5 memories (no reranking)."""
    return retrieve_memories(
        question=question,
        history=history,
        use_hybrid=use_hybrid,
        n_results=TOP_K,
    )


def match_trigger_rule(question: str) -> dict | None:
    """
    Check if the user's message matches any saved conditional rule trigger.
    Returns the matching memory dict if found, None otherwise.

    Example: if user said "remember: if I say 22, tell me I'm beautiful",
    then saying "22" later will match this rule.
    """
    try:
        memories = load_memories()
        q_lower = question.strip().lower()
        q_clean = q_lower.strip('"\'').strip()

        for mem in memories:
            trigger = mem.get("trigger", "").strip().lower().strip('"\'').strip()
            if not trigger:
                continue
            # Exact match or contains match
            if q_clean == trigger or trigger in q_clean or q_clean in trigger:
                return {
                    "memory_id": mem["memory_id"],
                    "title": mem.get("title", ""),
                    "category": mem.get("category", "rule"),
                    "emotion": mem.get("emotion", ""),
                    "snippet": mem["text"][:200],
                    "full_text": mem["text"],
                    "relevance_score": 1.0,
                    "trigger": trigger,
                    "response": mem.get("response", ""),
                    "is_rule": True,
                }
        return None
    except Exception as e:
        logger.warning(f"Trigger match failed: {e}")
        return None
