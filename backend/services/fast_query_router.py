"""Fast deterministic query router — no LLM calls."""
import re
from typing import Tuple

# Route constants
APP_IDENTITY = "app_identity"
CASUAL = "casual"
NORMAL_MEMORY = "normal_memory"
EXACT_MEMORY = "exact_memory"
TEMPORAL = "temporal"
UNFINISHED_THREAD = "unfinished_thread"

# Patterns
_APP_PATTERNS = [
    r"\bwho (are|made) you\b",
    r"\bwhat (are|is) you\b",
    r"\byour name\b",
    r"\bwho built\b",
    r"\bwhat can you do\b",
]

_CASUAL_PATTERNS = [
    r"^(hi|hey|hello|yo|sup|hola)\b",
    r"^how are you\b",
    r"^good (morning|evening|night|afternoon)\b",
    r"^thanks?\b",
    r"^thank you\b",
    r"^bye\b",
    r"^see you\b",
    r"^ok(ay)?\b",
    r"^nice\b",
    r"^cool\b",
]

_EXACT_PATTERNS = [
    r"\bwhat did i (say|tell|mention)\b",
    r"\bexact(ly)?\b",
    r"\bquote\b",
    r"\bverbatim\b",
    r"\bword for word\b",
    r"\bthe (bike|pizza|parrot|joke) (story|memory)\b",
]

_TEMPORAL_PATTERNS = [
    r"\blast (week|month|year|time)\b",
    r"\byesterday\b",
    r"\btoday\b",
    r"\brecently\b",
    r"\bwhen did\b",
    r"\bhow long ago\b",
]

_UNFINISHED_PATTERNS = [
    r"\bcontinue\b",
    r"\bgo on\b",
    r"\band then\b",
    r"\bwhat happened next\b",
    r"\btell me more\b",
]


def route_query(question: str, history: list = None) -> Tuple[str, dict]:
    """
    Classify a query into a route. Returns (route, metadata).

    Metadata keys:
      - skip_retrieval: bool
      - use_reranker: bool
      - n_results: int
      - reason: str
    """
    q = question.strip().lower()
    history = history or []

    # App identity
    for pat in _APP_PATTERNS:
        if re.search(pat, q):
            return APP_IDENTITY, {
                "skip_retrieval": True,
                "use_reranker": False,
                "n_results": 0,
                "reason": "app_identity_question",
            }

    # Casual
    for pat in _CASUAL_PATTERNS:
        if re.search(pat, q):
            return CASUAL, {
                "skip_retrieval": True,
                "use_reranker": False,
                "n_results": 0,
                "reason": "casual_greeting",
            }

    # Unfinished thread (follow-up)
    if history:
        for pat in _UNFINISHED_PATTERNS:
            if re.search(pat, q):
                return UNFINISHED_THREAD, {
                    "skip_retrieval": False,
                    "use_reranker": False,
                    "n_results": 5,
                    "reason": "follow_up_continuation",
                }

    # Exact memory
    for pat in _EXACT_PATTERNS:
        if re.search(pat, q):
            return EXACT_MEMORY, {
                "skip_retrieval": False,
                "use_reranker": True,
                "n_results": 12,
                "reason": "exact_memory_lookup",
            }

    # Temporal
    for pat in _TEMPORAL_PATTERNS:
        if re.search(pat, q):
            return TEMPORAL, {
                "skip_retrieval": False,
                "use_reranker": True,
                "n_results": 8,
                "reason": "temporal_query",
            }

    # Default: normal memory
    return NORMAL_MEMORY, {
        "skip_retrieval": False,
        "use_reranker": False,
        "n_results": 8,
        "reason": "default_memory_query",
    }
