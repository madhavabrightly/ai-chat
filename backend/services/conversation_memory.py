"""
Memory Twin AI — Conversation Memory Manager

Sliding-window conversation history with a token budget. Prevents the
context window from overflowing on long chats (Qwen2.5-7B has 32K context,
but long histories still slow generation and risk OOM).

Always keeps the most recent turns; trims older messages that exceed the
token budget. Guarantees at least the last 2 turns are retained.

References:
  - HuggingFace transformers chat templates + context management best practices
"""
import logging
from typing import List

logger = logging.getLogger(__name__)

# Reserve this many tokens for conversation history.
# Leaves room for system prompt + memory context + generation.
MAX_HISTORY_TOKENS = 2048


def _count_tokens(text: str, tokenizer) -> int:
    """Count tokens for a string (best-effort, falls back to char estimate)."""
    try:
        return len(tokenizer.encode(text))
    except Exception:
        # Rough fallback: ~4 chars per token for English
        return max(1, len(text) // 4)


def trim_history(history: List[dict], tokenizer, max_tokens: int = MAX_HISTORY_TOKENS) -> List[dict]:
    """
    Keep the most recent conversation turns within a token budget.

    Always retains at least the last 2 messages so the model has immediate
    context. Older messages are dropped from the front until the budget is met.
    """
    if not history or len(history) <= 2:
        return history

    trimmed = []
    token_count = 0
    for msg in reversed(history):
        msg_tokens = _count_tokens(msg.get("content", ""), tokenizer)
        # Stop once we exceed budget AND have at least 2 messages
        if token_count + msg_tokens > max_tokens and len(trimmed) >= 2:
            break
        trimmed.insert(0, msg)
        token_count += msg_tokens

    if len(trimmed) < len(history):
        logger.debug(f"Trimmed history {len(history)} → {len(trimmed)} msgs ({token_count} tokens)")

    return trimmed
