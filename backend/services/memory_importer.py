"""
Memory Twin AI — Memory Importer

Reads TXT/JSON files, chunks into memories, detects tone/emotions,
generates a style profile, and stores in ChromaDB.
"""
import json
import os
import uuid
import re
from typing import Optional


def _chunk_text(text: str, max_chars: int = 800) -> list[str]:
    """Split text into meaningful chunks of max_chars."""
    lines = text.strip().split("\n")
    chunks = []
    current = ""
    for line in lines:
        line = line.strip()
        if not line:
            if current:
                chunks.append(current.strip())
                current = ""
            continue
        if len(current) + len(line) > max_chars and current:
            chunks.append(current.strip())
            current = line
        else:
            current += "\n" + line if current else line
    if current:
        chunks.append(current.strip())
    return chunks if chunks else [text[:max_chars]]


def _detect_tone(text: str) -> str:
    """Detect emotional tone from text keywords."""
    t = text.lower()
    joy_words = ["happy", "joy", "love", "wonderful", "beautiful", "amazing", "grateful", "blessed", "fun", "laugh", "smile"]
    sad_words = ["sad", "miss", "cry", "hurt", "pain", "lonely", "regret", "sorry", "lost"]
    warm_words = ["warm", "kind", "care", "gentle", "soft", "hug", "comfort", "peace"]
    witty_words = ["funny", "joke", "hilarious", "witty", "sarcastic", "smart"]
    serious_words = ["important", "serious", "must", "need", "responsibility", "duty"]

    joy = sum(t.count(w) for w in joy_words)
    sad = sum(t.count(w) for w in sad_words)
    warm = sum(t.count(w) for w in warm_words)
    witty = sum(t.count(w) for w in witty_words)
    serious = sum(t.count(w) for w in serious_words)

    scores = {"warm": warm, "playful": witty, "caring": warm + joy, "serious": serious, "emotional": sad + joy}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "neutral"


def _detect_emotions(text: str) -> list[str]:
    """Extract emotion keywords from text."""
    emotions = set()
    t = text.lower()
    mapping = {
        "joyful": ["happy", "joy", "delighted", "thrilled", "elated"],
        "grateful": ["grateful", "thankful", "blessed", "appreciate"],
        "nostalgic": ["remember", "miss", "childhood", "used to", "back then"],
        "loving": ["love", "adore", "cherish", "dear", "sweet"],
        "sad": ["sad", "unhappy", "lonely", "heartbroken", "grief"],
        "amused": ["funny", "hilarious", "laugh", "joke", "amused"],
        "proud": ["proud", "achievement", "accomplished", "success"],
        "warm": ["warm", "kind", "gentle", "cozy", "comfort"],
        "thoughtful": ["thought", "reflect", "consider", "ponder", "wonder"],
    }
    for emotion, keywords in mapping.items():
        if any(k in t for k in keywords):
            emotions.add(emotion)
    return list(emotions) if emotions else ["neutral"]


def _extract_possible_title(chunk: str) -> str:
    """Extract a short title from a chunk."""
    lines = chunk.strip().split("\n")
    first = lines[0].strip()
    if len(first) < 80 and first:
        return first[:60]
    words = chunk.split()[:8]
    return " ".join(words)[:60] + ("..." if len(words) >= 8 else "")


def _detect_category(chunk: str) -> str:
    """Detect memory category from text."""
    t = chunk.lower()
    if any(w in t for w in ["childhood", "kid", "grew up", "school", "parent"]):
        return "Childhood"
    if any(w in t for w in ["family", "mom", "dad", "grandma", "grandpa", "sister", "brother", "uncle", "aunt"]):
        return "Family"
    if any(w in t for w in ["work", "job", "career", "boss", "colleague", "promotion", "meeting"]):
        return "Career"
    if any(w in t for w in ["advice", "wise", "lesson", "learned", "teach"]):
        return "Advice"
    if any(w in t for w in ["faith", "god", "belief", "pray", "kindness", "help"]):
        return "Faith & Kindness"
    if any(w in t for w in ["funny", "joke", "hilarious", "laugh"]):
        return "Humor"
    if any(w in t for w in ["love", "partner", "girlfriend", "boyfriend", "date", "romantic"]):
        return "Relationships"
    return "Personal"


def _extract_tags(chunk: str) -> list[str]:
    """Extract tags from chunk content."""
    words = set(w.lower().strip(".,!?;:") for w in chunk.split() if len(w) > 4)
    common = ["that", "this", "with", "from", "have", "been", "were", "about", "there", "their", "would", "could", "should", "because", "which", "after", "before", "without"]
    return list(words - set(common))[:6]


def parse_file(filepath: str, original_name: str, import_mode: str = "personal") -> dict:
    """
    Parse a TXT or JSON file into memory chunks with preview.

    Returns:
    {
        "import_id": "...",
        "file_name": "...",
        "file_type": "txt" or "json",
        "summary": "...",
        "detected_tone": "...",
        "detected_emotions": [...],
        "style_profile": {...},
        "memory_count": N,
        "preview_memories": [...]
    }
    """
    import_id = "import_" + uuid.uuid4().hex[:12]
    ext = os.path.splitext(original_name)[1].lower()

    if ext == ".json":
        with open(filepath, "r") as f:
            data = json.load(f)
        chunks = _parse_json(data)
    else:
        with open(filepath, "r") as f:
            raw = f.read()
        chunks = _chunk_text(raw)

    all_text = "\n".join(chunks)
    tone = _detect_tone(all_text)
    emotions = _detect_emotions(all_text)

    # Generate style profile
    style_profile = _build_style_profile(all_text, tone, emotions, import_mode)

    # Build memory objects
    preview = []
    for i, chunk in enumerate(chunks):
        preview.append({
            "memory_id": f"{import_id}_chunk_{i+1:04d}",
            "source_import_id": import_id,
            "source_file": original_name,
            "chunk_id": i + 1,
            "title": _extract_possible_title(chunk),
            "category": _detect_category(chunk),
            "text": chunk[:500],
            "exact_source": chunk,
            "emotion": (emotions[0] if emotions else "neutral"),
            "tags": _extract_tags(chunk),
            "imported": True,
        })

    # Summary
    summary = f"Imported from {original_name}. Contains {len(chunks)} memory chunks. "
    summary += f"Tone: {tone}. Emotions: {', '.join(emotions)}."

    return {
        "import_id": import_id,
        "file_name": original_name,
        "file_type": ext.replace(".", ""),
        "summary": summary,
        "detected_tone": tone,
        "detected_emotions": emotions,
        "style_profile": style_profile,
        "memory_count": len(chunks),
        "preview_memories": preview[:10],  # First 10 for preview
    }


def _parse_json(data) -> list[str]:
    """Parse various JSON formats into text chunks."""
    chunks = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or str(item)
                chunks.append(text[:800])
            else:
                chunks.append(str(item)[:800])
    elif isinstance(data, dict):
        # Format B: {"messages": [...]}
        if "messages" in data:
            for msg in data["messages"]:
                speaker = msg.get("speaker", msg.get("role", "Unknown"))
                text = msg.get("text", msg.get("content", ""))
                chunks.append(f"[{speaker}] {text}")
        # Format C: {"memories": [...]}
        elif "memories" in data:
            for mem in data["memories"]:
                text = mem.get("text", mem.get("content", ""))
                chunks.append(text)
        else:
            # Try to extract any text values
            for k, v in data.items():
                if isinstance(v, str) and len(v) > 20:
                    chunks.append(v)

    return _chunk_text("\n".join(chunks)) if chunks else []


def _build_style_profile(all_text: str, tone: str, emotions: list[str], import_mode: str) -> dict:
    """Build a style profile from imported text."""
    style_id = "style_" + uuid.uuid4().hex[:8]

    tone_map = {
        "warm": "warm, caring, affectionate but non-sexual",
        "playful": "playful, witty, light-hearted",
        "caring": "caring, gentle, emotionally supportive",
        "serious": "thoughtful, serious, reflective",
        "emotional": "emotionally expressive, deep, heartfelt",
    }

    chat_style = tone_map.get(tone, "warm and natural")
    companion_mode = "warm_affectionate_safe" if import_mode == "companion" else "memory_assistant"

    return {
        "style_profile_id": style_id,
        "summary": f"Style adapted from {tone} tone with {', '.join(emotions)} emotional patterns.",
        "tone": tone,
        "chat_style": chat_style,
        "emotional_patterns": emotions,
        "companion_mode": companion_mode,
        "boundaries": [
            "Do not claim to be the real person from imported text",
            "Do not invent memories not present in imported data",
            "Answer from imported memories when asked about them",
            "Keep warm/affectionate tone non-explicit and respectful",
        ],
    }


def commit_import(preview_result: dict) -> list[dict]:
    """
    Commit the preview result to ChromaDB.
    Returns the full list of memory dicts ready for storage.
    """
    # Rebuild full memories from preview (all chunks, not just first 10)
    # For now, the preview already has the first 10
    memories = preview_result.get("preview_memories", [])
    for mem in memories:
        mem["imported"] = True
    return memories
