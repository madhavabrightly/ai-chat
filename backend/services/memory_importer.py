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
            timestamp_iso TEXT DEFAULT '',
            text TEXT NOT NULL,
            exact_source TEXT NOT NULL,
            line_number INTEGER DEFAULT 0,
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
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_line ON messages(line_number)
    """)
    conn.commit()
    conn.close()


def _parse_whatsapp_line(line: str, line_number: int = 0) -> dict | None:
    """Parse a single WhatsApp line into {speaker, date, text, line_number}."""
    line = line.strip()
    if not line:
        return None

    m = WA1.match(line)
    if m:
        return {
            "speaker": m.group(2).strip(),
            "date": m.group(1).strip(),
            "text": m.group(3).strip(),
            "exact_source": line,
            "line_number": line_number,
        }

    m = WA2.match(line)
    if m:
        return {
            "speaker": m.group(2).strip(),
            "date": m.group(1).strip(),
            "text": m.group(3).strip(),
            "exact_source": line,
            "line_number": line_number,
        }

    m = WA3.match(line)
    if m:
        return {
            "speaker": m.group(1).strip(),
            "date": "",
            "text": m.group(2).strip(),
            "exact_source": line,
            "line_number": line_number,
        }

    return {"speaker": "", "date": "", "text": line, "exact_source": line, "line_number": line_number}


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
        date_str = msg.get("date", "")
        timestamp_iso = _normalize_date_to_iso(date_str)
        messages.append({
            "id": mid,
            "session_id": session_id,
            "source_file": original_name,
            "speaker": msg.get("speaker", ""),
            "date": date_str,
            "timestamp_iso": timestamp_iso,
            "text": msg.get("text", ""),
            "exact_source": msg.get("exact_source", msg.get("text", "")),
            "line_number": msg.get("line_number", 0),
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
        INSERT OR IGNORE INTO messages (id, session_id, source_file, speaker, date, timestamp_iso, text, exact_source, line_number, emotion, tags, chunk_group)
        VALUES (:id, :session_id, :source_file, :speaker, :date, :timestamp_iso, :text, :exact_source, :line_number, :emotion, :tags, :chunk_group)
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
    """Parse raw WhatsApp text into per-message dicts with line numbers."""
    lines = raw.split("\n")
    messages = []
    for line_no, line in enumerate(lines, start=1):
        parsed = _parse_whatsapp_line(line, line_number=line_no)
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

    for idx, item in enumerate(items, start=1):
        if isinstance(item, dict):
            speaker = item.get("speaker") or item.get("role") or ""
            date = item.get("date") or item.get("timestamp") or item.get("datetime") or ""
            text = item.get("text") or item.get("content") or item.get("message") or json.dumps(item)
            messages.append({
                "speaker": speaker,
                "date": date,
                "text": str(text),
                "exact_source": json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item),
                "line_number": idx,
            })

    return messages


def _normalize_date_to_iso(date_str: str) -> str:
    """
    Normalize a WhatsApp-style date string to ISO 8601 (best-effort).
    Returns '' if parsing fails. Used for temporal filtering.
    """
    if not date_str:
        return ""
    try:
        from datetime import datetime
        s = date_str.strip()
        # Try common WhatsApp formats
        for fmt in (
            "%d/%m/%Y, %H:%M",
            "%m/%d/%Y, %H:%M",
            "%d-%m-%Y, %H:%M",
            "%d/%m/%Y %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(s, fmt)
                return dt.isoformat()
            except ValueError:
                continue
        return s  # keep original if no format matched
    except Exception:
        return ""


def _index_messages_in_chroma(session_id: str, messages: list[dict]):
    """
    Index messages in a session-level Chroma collection using REAL Qwen3
    embeddings (not fake hash-based vectors). Falls back to skipping indexing
    if the embedding model is unavailable.
    """
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
        collection = client.get_or_create_collection(
            name=collection_name,
            configuration={"hnsw": {"space": "cosine", "ef_construction": 200, "ef_search": 100, "max_neighbors": 16}},
        )

        ids = [m["id"] for m in messages if m["text"].strip()]
        texts = [m["text"] for m in messages if m["text"].strip()]
        metadatas = [
            {
                "speaker": m["speaker"],
                "date": m["date"],
                "timestamp_iso": m.get("timestamp_iso", ""),
                "session_id": session_id,
                "source_file": m["source_file"],
                "line_number": m.get("line_number", 0),
                "chunk_group": m.get("chunk_group", 0),
            }
            for m in messages if m["text"].strip()
        ]

        if ids:
            # Use REAL Qwen3-Embedding vectors (not fake hash-based ones)
            try:
                from backend.models.embedding_loader import embed_documents
                embeddings = embed_documents(texts)
                collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
            except Exception as emb_err:
                # If the embedding model isn't loaded, store docs without
                # embeddings so ChromaDB can still do brute-force text search
                print(f"[IMPORTER] Real embeddings unavailable, storing docs only: {emb_err}")
                collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
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
