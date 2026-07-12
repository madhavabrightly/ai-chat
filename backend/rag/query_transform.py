"""Query transformation utilities: RRF fusion + question condensing."""
import logging
from typing import List

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(rankings: List[List[str]], k: int = 60) -> List[tuple]:
    """
    Reciprocal Rank Fusion (RAG-Fusion, Wang et al. 2024).

    Combines multiple ranked lists into a single ranking.
    Each document's score = sum of 1/(k + rank_i) across all rankings.

    Args:
        rankings: list of ranked lists of document IDs
        k: constant (default 60, from original paper)

    Returns:
        list of (doc_id, fused_score) sorted by score descending
    """
    scores = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            if doc_id not in scores:
                scores[doc_id] = 0.0
            scores[doc_id] += 1.0 / (k + rank + 1)

    return sorted(scores.items(), key=lambda x: -x[1])


def condense_question(question: str, history: List[dict]) -> str:
    """
    Condense a follow-up question into a standalone query using chat history.

    Pattern from LlamaIndex chat_engine/condense_plus_context.py.
    Uses simple heuristic — if the question is short and references prior context,
    prepend the last user message topic.

    Args:
        question: the current user question
        history: list of {"role": ..., "content": ...} dicts

    Returns:
        a standalone query string
    """
    if not history:
        return question

    # Heuristic: if question is short (< 6 words) and contains pronouns/refs,
    # prepend the last user message
    q_lower = question.lower().strip()
    short = len(q_lower.split()) < 6
    has_ref = any(w in q_lower for w in ["it", "that", "this", "they", "them", "those", "he", "she"])

    if not (short and has_ref):
        return question

    # Find last user message in history
    for msg in reversed(history):
        if msg.get("role") == "user":
            last_user = msg.get("content", "").strip()
            if last_user:
                # Combine: last user topic + current question
                return f"{last_user} — {question}"
            break

    return question
