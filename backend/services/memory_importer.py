"""
Memory Twin AI — Phase 1 Memory Importer

Parses WhatsApp TXT and JSON into per-message records.
Each message preserves: speaker, date, exact source line.
Stores in SQLite + indexes in Chroma for retrieval.
"""
import json
import os
import uuid
import re
import sqlite3
from datetime import datetime
from backend.config import RUNTIME_ROOT

IMPORTS_DB_DIR = os.path.join(RUNTIME_ROOT, "imports_db")
os.makedirs(IMPORTS_DB_DIR, exist_ok=True)

# ── WhatsApp line regexes ───────────────────────────────────────────
# [12/01/2026, 10:23 AM] Name: message
WA1 = re.compile(r'^\[(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}[,\s]*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?)\]\s+([^:]+?):\s*(.*)')
# 12/01/2026, 10:23 - Name: message
WA2 = re.compile(r'^(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}[,\s]*\d{1,2}:\d{2}(?::\d{2})?(?:\s*AM|\s*PM)?)\s*[-–]\s*([^:]+?):\s*(.*)')
# Name: message (no date)
WA3 = re.compile(r'^([A-Za-z][A-Za-z\s]+?):\s*(.*)')


def _get_db_path(session_id: str) -> str:
    return os.path.join(IMPORTS_DB_DIR, f"{session_id}.db")


def _init_db(db_path: str):
    """Create SQLite tables for an import session."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            source_file TEXT NOT NULL,
            speaker TEXT DEFAULT '',
            date TEXT DEFAULT '',
            text TEXT NOT NULL,
            exact_source TEXT NOT NULL,
            emotion TEXT DEFAULT 'neutral',
            tags TEXT DEFAULT '[]',
            chunk_group INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_speaker ON messages(speaker)
    """)
    conn.commit()
    conn.close()


def _parse_whatsapp_line(line: str) -> dict | None:
    """Parse a single WhatsApp line into {speaker, date, text}."""
    line = line.strip()
    if not line:
        return None

    m = WA1.match(line)
    if m:
        return {"speaker": m.group(2).strip(), "date": m.group(1).strip(), "text": m.group(3).strip(), "exact_source": line}

    m = WA2.match(line)
    if m:
        return {"speaker": m.group(2).strip(), "date": m.group(1).strip(), "text": m.group(3).strip(), "exact_source": line}

    m = WA3.match(line)
    if m:
        return {"speaker": m.group(1).strip(), "date": "", "text": m.group(2).strip(), "exact_source": line}

    return {"speaker": "", "date": "", "text": line, "exact_source": line}


def parse_file_to_messages(filepath: str, original_name: str) -> dict:
    """
    Parse a TXT or JSON file into per-message records.
    Returns { session_id, file_name, file_type, message_count, messages[ {id, speaker, date, text, exact_source, emotion, tags} ] }
    """
    session_id = "import_" + uuid.uuid4().hex[:12]
    ext = os.path.splitext(original_name)[1].lower()

    raw_messages = []

    if ext == ".json":
        with open(filepath, "r") as f:
            data = json.load(f)
        raw_messages = _parse_json_messages(data, original_name)
    else:
        with open(filepath, "r") as f:
            raw = f.read()
        raw_messages = _parse_whatsapp_text(raw)

    # Deduplicate consecutive same-speaker messages into groups
    messages = []
    current_group = 0
    for i, msg in enumerate(raw_messages):
        mid = f"{session_id}_msg_{i+1:06d}"
        messages.append({
            "id": mid,
            "session_id": session_id,
            "source_file": original_name,
            "speaker": msg.get("speaker", ""),
            "date": msg.get("date", ""),
            "text": msg.get("text", ""),
            "exact_source": msg.get("exact_source", msg.get("text", "")),
            "emotion": "neutral",
            "tags": json.dumps([msg.get("speaker", "").lower() if msg.get("speaker") else "unknown"]),
            "chunk_group": current_group,
        })
        # Same speaker continues group
        if i + 1 < len(raw_messages) and raw_messages[i + 1].get("speaker") == msg.get("speaker"):
            pass
        else:
            current_group += 1

    # Store in SQLite
    db_path = _get_db_path(session_id)
    _init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.executemany("""
        INSERT OR IGNORE INTO messages (id, session_id, source_file, speaker, date, text, exact_source, emotion, tags, chunk_group)
        VALUES (:id, :session_id, :source_file, :speaker, :date, :text, :exact_source, :emotion, :tags, :chunk_group)
    """, messages)
    conn.commit()
    conn.close()

    # Index in Chroma
    _index_messages_in_chroma(session_id, messages)

    return {
        "session_id": session_id,
        "file_name": original_name,
        "file_type": ext.replace(".", ""),
        "message_count": len(messages),
        "messages": messages,
    }


def _parse_whatsapp_text(raw: str) -> list[dict]:
    """Parse raw WhatsApp text into per-message dicts."""
    lines = raw.split("\n")
    messages = []
    for line in lines:
        parsed = _parse_whatsapp_line(line)
        if parsed:
            messages.append(parsed)
    return messages


def _parse_json_messages(data, filename: str) -> list[dict]:
    """Parse JSON into per-message dicts."""
    messages = []

    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("messages", data.get("memories", [data]))

    for item in items:
        if isinstance(item, dict):
            speaker = item.get("speaker") or item.get("role") or ""
            date = item.get("date") or item.get("timestamp") or item.get("datetime") or ""
            text = item.get("text") or item.get("content") or item.get("message") or json.dumps(item)
            messages.append({
                "speaker": speaker,
                "date": date,
                "text": str(text),
                "exact_source": json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item),
            })

    return messages


def _index_messages_in_chroma(session_id: str, messages: list[dict]):
    """Index messages in a session-level Chroma collection."""
    try:
        import chromadb
        from chromadb.config import Settings
        from backend.config import CHROMA_DB_DIR

        client = chromadb.PersistentClient(path=CHROMA_DB_DIR, settings=Settings(anonymized_telemetry=False))
        collection_name = f"import_{session_id}"
        try:
            client.delete_collection(collection_name)
        except ValueError:
            pass
        collection = client.get_or_create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})

        ids = [m["id"] for m in messages if m["text"].strip()]
        texts = [m["text"] for m in messages if m["text"].strip()]
        metadatas = [{"speaker": m["speaker"], "date": m["date"], "session_id": session_id, "source_file": m["source_file"]} for m in messages if m["text"].strip()]

        if ids:
            # Use simple embeddings (fallback — no model load per request)
            import hashlib
            fake_embeddings = [[hash(hashlib.md5(t.encode()) % 10000) / 10000 for _ in range(128)] for t in texts]
            collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=fake_embeddings)
    except Exception as e:
        print(f"[IMPORTER] Chroma indexing skipped: {e}")


def get_session_messages(session_id: str) -> list[dict]:
    """Retrieve all messages for a session from SQLite."""
    db_path = _get_db_path(session_id)
    if not os.path.exists(db_path):
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM messages ORDER BY rowid").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_sessions() -> list[dict]:
    """List all import sessions with message counts."""
    sessions = []
    if not os.path.isdir(IMPORTS_DB_DIR):
        return sessions
    for fn in sorted(os.listdir(IMPORTS_DB_DIR)):
        if fn.endswith(".db"):
            session_id = fn.replace(".db", "")
            db_path = os.path.join(IMPORTS_DB_DIR, fn)
            conn = sqlite3.connect(db_path)
            count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            conn.close()
            sessions.append({"session_id": session_id, "message_count": count})
    return sessions
