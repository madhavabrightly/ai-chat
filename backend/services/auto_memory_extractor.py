"""
Auto Memory Extractor
=====================

Detects when a user asks the AI to "remember" something and automatically
extracts the fact into a persistent memory. This solves the problem where
the AI agrees to remember something but never actually saves it.

Patterns detected:
- "remember that [fact]"
- "remember [fact]"
- "if I say X, [fact]"
- "when I say X, [fact]"
- "my name is X"
- "I am X"
- "I like X"
- "I love X"
- "I hate X"
- "call me X"
- "I'm X years old"

The extracted memory is:
1. Saved to the JSON file (persistent)
2. Embedded and added to ChromaDB (retrievable)
3. Bumped in the service container cache (so next query sees it)
"""

import json
import logging
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Path to memories JSON file — use the same path as memory_store.py
try:
    from backend.config import MEMORIES_PATH as _CONFIG_MEMORIES_PATH
    MEMORIES_PATH = Path(_CONFIG_MEMORIES_PATH)
except Exception:
    # Fallback
    MEMORIES_PATH = Path("/workspace/projects/ai-chat/backend/data/memories.json")

# Lock for thread-safe writes
_write_lock = threading.Lock()

# Dangerous patterns that should NEVER be saved as memories
# These indicate SQL injection, code injection, or prompt injection attempts
# NOTE: We use CONTEXTUAL detection — single SQL keywords like "WHERE" in
# natural English are NOT flagged. Only actual injection patterns are caught.
_DANGEROUS_PATTERNS = [
    # SQL DDL/DML with semicolon (e.g., "DROP TABLE x;", "DELETE FROM x;")
    re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b\s+(\*|\w+)\s+FROM\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+(TABLE|DATABASE|INDEX|VIEW|SCHEMA)\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\s+(TABLE\s+)?\w+", re.IGNORECASE),
    # SQL comment markers (-- or /* */)
    re.compile(r";\s*--|/\*|\*/"),
    # SQL string termination + OR injection (e.g., "' OR 1=1 --")
    re.compile(r"['\"]\s*OR\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+", re.IGNORECASE),
    re.compile(r"['\"]\s*OR\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+", re.IGNORECASE),
    re.compile(r"\bUNION\s+SELECT\b", re.IGNORECASE),
    # Prompt injection markers
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|above)", re.IGNORECASE),
    # Excessive special characters (likely garbage input)
    re.compile(r"[;]{2,}|[.]{3,}[;]|[,;.]{5,}"),
]

# Regex patterns for memory extraction
# Order matters — more specific patterns first
PATTERNS = [
    # "remember that X" / "remember X"
    (re.compile(r"remember\s+that\s+(.+?)(?:\?|$|\.)", re.IGNORECASE), "explicit_remember"),
    (re.compile(r"please\s+remember\s+(.+?)(?:\?|$|\.)", re.IGNORECASE), "explicit_remember"),
    (re.compile(r"can\s+you\s+remember\s+(.+?)(?:\?|$|\.)", re.IGNORECASE), "explicit_remember"),
    # "if I say X, you need to tell Y" / "if I say X, [fact]"
    (re.compile(r"if\s+i\s+say\s+[\"']?(.+?)[\"']?[,]?\s+(?:you\s+(?:need\s+to|should|must|will)\s+(?:tell|say|respond|reply)\s+(?:me\s+)?)?(.+?)(?:\?|$|\.)", re.IGNORECASE), "conditional_rule"),
    # "when I say X, Y"
    (re.compile(r"when\s+i\s+say\s+[\"']?(.+?)[\"']?[,]?\s+(.+?)(?:\?|$|\.)", re.IGNORECASE), "conditional_rule"),
    # "my name is X"
    (re.compile(r"my\s+name\s+is\s+([A-Za-z][A-Za-z\s]{1,30})", re.IGNORECASE), "identity"),
    # "call me X"
    (re.compile(r"call\s+me\s+([A-Za-z][A-Za-z\s]{1,30})", re.IGNORECASE), "identity"),
    # "I am X years old"
    (re.compile(r"i\s+am\s+(\d{1,3})\s+years?\s+old", re.IGNORECASE), "identity"),
    # "I'm X"
    (re.compile(r"i'?m\s+([A-Za-z][A-Za-z\s]{1,30})", re.IGNORECASE), "identity"),
    # "I like X" / "I love X" / "I hate X"
    (re.compile(r"i\s+(?:really\s+)?(?:like|love|enjoy|prefer)\s+(.+?)(?:\?|$|\.)", re.IGNORECASE), "preference"),
    (re.compile(r"i\s+(?:really\s+)?(?:hate|dislike|can't\s+stand)\s+(.+?)(?:\?|$|\.)", re.IGNORECASE), "preference"),
    # "I work as X" / "I am a X"
    (re.compile(r"i\s+(?:work\s+as|am\s+a)\s+([A-Za-z][A-Za-z\s]{1,40})", re.IGNORECASE), "identity"),
    # "I live in X"
    (re.compile(r"i\s+live\s+in\s+([A-Za-z][A-Za-z\s,]{1,40})", re.IGNORECASE), "identity"),
]


def _is_dangerous_input(text: str) -> bool:
    """
    Check if input contains SQL injection, code injection, or prompt injection patterns.
    Returns True if the input should be rejected.
    """
    if not text:
        return False
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _sanitize_text(text: str, max_length: int = 500) -> str:
    """
    Sanitize text for safe storage:
    - Strip leading/trailing whitespace
    - Remove null bytes and control characters
    - Collapse excessive whitespace
    - Truncate to max_length
    """
    if not text:
        return ""
    # Remove null bytes and control characters (except newlines/tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Collapse multiple spaces (but keep newlines)
    text = re.sub(r"[ \t]+", " ", text)
    # Strip
    text = text.strip()
    # Truncate
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0] + "..."
    return text


def extract_memory_from_message(message: str) -> Optional[dict]:
    """
    Try to extract a memory from a user message.
    Returns a dict with 'text', 'category', 'tags' or None if no pattern matches.
    """
    if not message or len(message.strip()) < 3:
        return None

    msg = message.strip()

    # Reject dangerous inputs (SQL injection, code injection, prompt injection)
    if _is_dangerous_input(msg):
        logger.warning(f"[AUTO-MEMORY] Rejected dangerous input: {msg[:80]}")
        return None

    for pattern, category in PATTERNS:
        match = pattern.search(msg)
        if match:
            groups = match.groups()

            if category == "conditional_rule":
                # "if I say X, Y" — extract the rule
                trigger = _sanitize_text(groups[0].strip().strip('"\''), max_length=100)
                response = _sanitize_text(groups[1].strip(), max_length=300) if len(groups) > 1 else ""
                if not response:
                    continue
                # Re-check sanitized parts for danger
                if _is_dangerous_input(trigger) or _is_dangerous_input(response):
                    logger.warning(f"[AUTO-MEMORY] Rejected dangerous rule: trigger={trigger[:50]}")
                    return None
                text = f"When the user says \"{trigger}\", respond: {response}"
                tags = ["conditional", "rule", "trigger"]
                return {
                    "text": text,
                    "category": "rule",
                    "tags": tags,
                    "trigger": trigger,
                    "response": response,
                }
            elif category == "explicit_remember":
                fact = _sanitize_text(groups[0].strip(), max_length=400)
                if len(fact) < 2:
                    continue
                # Re-check sanitized fact for danger
                if _is_dangerous_input(fact):
                    logger.warning(f"[AUTO-MEMORY] Rejected dangerous fact: {fact[:50]}")
                    return None
                text = f"User asked to remember: {fact}"
                return {
                    "text": text,
                    "category": "explicit_fact",
                    "tags": ["remember", "explicit"],
                }
            elif category == "identity":
                value = _sanitize_text(groups[0].strip(), max_length=50)
                if not value:
                    continue
                if _is_dangerous_input(value):
                    logger.warning(f"[AUTO-MEMORY] Rejected dangerous identity: {value[:50]}")
                    return None
                if "years old" in msg.lower():
                    text = f"User is {value} years old"
                    return {
                        "text": text,
                        "category": "identity",
                        "tags": ["age", "identity"],
                    }
                # Generic identity
                text = f"User identity: {value}"
                return {
                    "text": text,
                    "category": "identity",
                    "tags": ["identity", "self"],
                }
            elif category == "preference":
                value = _sanitize_text(groups[0].strip(), max_length=200)
                if not value:
                    continue
                if _is_dangerous_input(value):
                    logger.warning(f"[AUTO-MEMORY] Rejected dangerous preference: {value[:50]}")
                    return None
                # Detect like vs hate
                if any(w in msg.lower() for w in ["hate", "dislike", "can't stand"]):
                    text = f"User dislikes: {value}"
                    tags = ["preference", "dislike"]
                else:
                    text = f"User likes: {value}"
                    tags = ["preference", "like"]
                return {
                    "text": text,
                    "category": "preference",
                    "tags": tags,
                }

    return None


def _generate_memory_id(existing_ids: set) -> str:
    """Generate a unique memory ID."""
    i = 1
    while True:
        mid = f"auto_{i:04d}"
        if mid not in existing_ids:
            return mid
        i += 1


def save_extracted_memory(memory: dict) -> Optional[str]:
    """
    Save an extracted memory to the JSON file and ChromaDB.
    Returns the memory_id if successful, None otherwise.
    """
    try:
        with _write_lock:
            # Load existing memories
            if MEMORIES_PATH.exists():
                with open(MEMORIES_PATH, "r") as f:
                    memories = json.load(f)
            else:
                memories = []

            # Generate unique ID
            existing_ids = {m.get("memory_id", "") for m in memories}
            memory_id = _generate_memory_id(existing_ids)

            # Build memory entry
            entry = {
                "memory_id": memory_id,
                "title": memory["text"][:60] + ("..." if len(memory["text"]) > 60 else ""),
                "text": memory["text"],
                "category": memory.get("category", "auto_extracted"),
                "emotion": "neutral",
                "tags": memory.get("tags", []),
                "source": "auto_extracted",
                "created_at": datetime.utcnow().isoformat() + "Z",
            }

            # Add trigger/response if conditional rule
            if "trigger" in memory:
                entry["trigger"] = memory["trigger"]
                entry["response"] = memory["response"]

            memories.append(entry)

            # Save to file
            MEMORIES_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(MEMORIES_PATH, "w") as f:
                json.dump(memories, f, indent=2)

            logger.info(f"[AUTO-MEMORY] Saved {memory_id}: {memory['text'][:80]}")

            # Add to ChromaDB
            try:
                from backend.rag.memory_store import _get_collection
                from backend.core.service_container import ServiceContainer

                collection = _get_collection()
                container = ServiceContainer.get()

                # Use embedder from service container if available, else load it
                if container.embedder_model is not None:
                    embedding = container.embedder_model.encode([memory["text"]], prompt_name="query", convert_to_numpy=True).tolist()[0]
                else:
                    from backend.models.embedding_loader import embed_documents
                    embedding = embed_documents([memory["text"]])[0]

                collection.upsert(
                    ids=[memory_id],
                    embeddings=[embedding],
                    documents=[memory["text"]],
                    metadatas=[{
                        "memory_id": memory_id,
                        "title": entry["title"],
                        "category": entry["category"],
                        "emotion": entry["emotion"],
                        "tags": ", ".join(entry["tags"]),
                    }],
                )
                logger.info(f"[AUTO-MEMORY] Added {memory_id} to ChromaDB")
            except Exception as e:
                logger.warning(f"[AUTO-MEMORY] ChromaDB upsert failed: {e}")

            # Bump memory version in service container
            try:
                from backend.core.service_container import ServiceContainer
                container = ServiceContainer.get()
                container.bump_memory_version()
                logger.info(f"[AUTO-MEMORY] Bumped memory version to {container.memory_version}")
            except Exception as e:
                logger.warning(f"[AUTO-MEMORY] Could not bump memory version: {e}")

            return memory_id

    except Exception as e:
        logger.error(f"[AUTO-MEMORY] Failed to save memory: {e}")
        return None


def check_and_extract(user_message: str) -> Optional[str]:
    """
    Check a user message for memory-worthy content and save if found.
    Returns the memory_id if a memory was saved, None otherwise.
    """
    memory = extract_memory_from_message(user_message)
    if memory is None:
        return None
    return save_extracted_memory(memory)
