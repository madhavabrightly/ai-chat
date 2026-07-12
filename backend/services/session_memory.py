"""Fast per-session memory log and retrieval.

This stores recent chat turns outside git under RUNTIME_ROOT and optionally
indexes them into Chroma for faster semantic recall.
"""
import json
import os
import tempfile
import threading
import time
import uuid
from datetime import datetime

from backend.config import RUNTIME_ROOT

SESSION_DIR = os.path.join(RUNTIME_ROOT, "session_memory")
SESSION_JSON_PATH = os.path.join(SESSION_DIR, "session_log.json")
MAX_SESSION_ITEMS = 5000

_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _load_items() -> list[dict]:
    if not os.path.exists(SESSION_JSON_PATH):
        return []
    try:
        with open(SESSION_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []


def _write_items(items: list[dict]) -> None:
    os.makedirs(SESSION_DIR, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".json", dir=SESSION_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(items[-MAX_SESSION_ITEMS:], f, indent=2, ensure_ascii=False)
        os.replace(tmp, SESSION_JSON_PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def append_session_message(
    role: str,
    content: str,
    companion_type: str = "female",
    request_id: str | None = None,
) -> dict | None:
    text = (content or "").strip()
    if not text:
        return None

    entry = {
        "id": f"session_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}",
        "request_id": request_id or "",
        "role": role,
        "content": text[:4000],
        "companion_type": companion_type,
        "created_at": _now_iso(),
    }
    with _lock:
        items = _load_items()
        items.append(entry)
        _write_items(items)

    _index_session_entry(entry)
    return entry


def retrieve_session_memories(query: str, n_results: int = 6) -> list[dict]:
    question = (query or "").strip()
    if not question:
        return []

    semantic = _semantic_search(question, n_results=n_results)
    if semantic:
        return semantic

    with _lock:
        items = _load_items()

    q_terms = {t for t in question.lower().split() if len(t) > 2}
    scored = []
    for item in items:
        content = item.get("content", "")
        terms = set(content.lower().split())
        overlap = len(q_terms & terms)
        recency = len(scored) / max(len(items), 1)
        score = overlap + recency * 0.05
        if overlap > 0 or item.get("role") == "user":
            scored.append((score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    if not scored:
        scored = [(0, item) for item in items[-n_results:]]
    return [_to_memory(item, score) for score, item in scored[:n_results]]


def _index_session_entry(entry: dict) -> None:
    try:
        from backend.models.embedding_loader import embed_documents
        from backend.rag.memory_store import _get_collection
        from backend.core.service_container import ServiceContainer

        doc = f"{entry['role']}: {entry['content']}"
        embedding = embed_documents([doc])[0]
        collection = _get_collection()
        collection.upsert(
            ids=[entry["id"]],
            embeddings=[embedding],
            documents=[doc],
            metadatas=[{
                "memory_id": entry["id"],
                "title": "Live session memory",
                "category": "Session",
                "emotion": "Live",
                "tags": "session,chat",
            }],
        )
        ServiceContainer.get().bump_memory_version()
    except Exception:
        return


def _semantic_search(query: str, n_results: int) -> list[dict]:
    try:
        from backend.models.embedding_loader import embed_query
        from backend.rag.memory_store import _get_collection

        collection = _get_collection()
        results = collection.query(
            query_embeddings=[embed_query(query)],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
            where={"category": "Session"},
        )
        memories = []
        for i, mem_id in enumerate(results.get("ids", [[]])[0]):
            meta = results["metadatas"][0][i]
            doc = results["documents"][0][i]
            distance = results["distances"][0][i] if results.get("distances") else None
            memories.append({
                "memory_id": mem_id,
                "title": meta.get("title", "Live session memory"),
                "category": "Session",
                "emotion": meta.get("emotion", "Live"),
                "snippet": doc[:200] + ("..." if len(doc) > 200 else ""),
                "full_text": doc,
                "relevance_score": round(1.0 - distance, 4) if distance is not None else None,
                "source": "session_json",
            })
        return memories
    except Exception:
        return []


def _to_memory(item: dict, score: float) -> dict:
    doc = f"{item.get('role', 'chat')}: {item.get('content', '')}"
    return {
        "memory_id": item.get("id", ""),
        "title": "Live session memory",
        "category": "Session",
        "emotion": "Live",
        "snippet": doc[:200] + ("..." if len(doc) > 200 else ""),
        "full_text": doc,
        "relevance_score": round(float(score), 4),
        "source": "session_json",
    }
