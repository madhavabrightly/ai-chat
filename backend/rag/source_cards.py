"""
Memory Twin AI — Source Card Builder

Builds exact source cards for the frontend. Each card contains:
  - speaker (who said it)
  - timestamp (when it was said)
  - file (which imported file)
  - line_number (which line in the file)
  - exact_source (the verbatim line)
  - text (the message content)

Source cards are displayed in the UI so the user can trace every claim
back to its origin. This is the visible half of the Memory Truth Contract.
"""
import logging

logger = logging.getLogger(__name__)


def build_source_card(memory: dict) -> dict:
    """
    Build a single source card from a memory dict.

    Args:
      memory: dict with keys like speaker, date, timestamp_iso, source_file,
              line_number, exact_source, text, full_text

    Returns:
      {
        "speaker": str,
        "timestamp": str,         # human-readable
        "timestamp_iso": str,     # ISO 8601 for sorting
        "file": str,
        "line_number": int,
        "exact_source": str,      # verbatim line
        "text": str,              # message content
        "memory_id": str,
        "title": str,
        "category": str,
        "relevance_score": float,
      }
    """
    return {
        "speaker": memory.get("speaker", "") or "Unknown",
        "timestamp": memory.get("date", "") or memory.get("timestamp_iso", ""),
        "timestamp_iso": memory.get("timestamp_iso", "") or memory.get("date", ""),
        "file": memory.get("source_file", "") or memory.get("title", ""),
        "line_number": memory.get("line_number", 0) or 0,
        "exact_source": memory.get("exact_source", "") or memory.get("full_text", "")[:200],
        "text": memory.get("text", "") or memory.get("full_text", ""),
        "memory_id": memory.get("memory_id", "") or memory.get("id", ""),
        "title": memory.get("title", ""),
        "category": memory.get("category", ""),
        "relevance_score": memory.get("relevance_score", 0) or memory.get("fused_score", 0) or 0,
    }


def build_source_cards(memories: list[dict]) -> list[dict]:
    """
    Build source cards for a list of memories.

    Returns a list of card dicts, one per memory, sorted by relevance_score
    descending.
    """
    cards = [build_source_card(m) for m in memories]
    cards.sort(key=lambda c: c.get("relevance_score", 0), reverse=True)
    return cards


def format_source_card_text(card: dict) -> str:
    """
    Format a source card as a human-readable string for display in the UI.
    """
    parts = []
    if card.get("speaker"):
        parts.append(f"👤 {card['speaker']}")
    if card.get("timestamp"):
        parts.append(f"🕐 {card['timestamp']}")
    if card.get("file"):
        line_info = f"line {card['line_number']}" if card.get("line_number") else ""
        if line_info:
            parts.append(f"📄 {card['file']} ({line_info})")
        else:
            parts.append(f"📄 {card['file']}")
    if card.get("relevance_score"):
        parts.append(f"⭐ {card['relevance_score']:.2f}")
    header = " | ".join(parts)
    quote = card.get("exact_source", "") or card.get("text", "")
    return f"{header}\n\"{quote}\""
