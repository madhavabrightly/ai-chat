"""
Memory Twin AI — Question Classifier

Classifies user questions into one of 7 categories so the retrieval + answer
pipeline can apply the right strategy:

  - EXACT_QUOTE          : "What did X say on Y?" — needs verbatim source line
  - TEMPORAL_COMPARISON  : "What did I do last week vs this week?" — needs date filter
  - UNFINISHED_THREAD    : "You never finished telling me about..." — needs follow-up
  - PERSONAL_FACT        : "What's my favorite color?" — needs personal fact lookup
  - SUPPORTED_INFERENCE  : "Why did I feel that way?" — needs inference from evidence
  - GENERAL_COMPANION    : "How are you today?" — no retrieval needed
  - APP_IDENTITY         : "Who are you?" — no retrieval needed

Uses deterministic keyword/regex rules first (fast, no LLM cost), then falls
back to a small LLM call only when confidence is low.
"""
import logging
import re

logger = logging.getLogger(__name__)

# Question categories
EXACT_QUOTE = "EXACT_QUOTE"
TEMPORAL_COMPARISON = "TEMPORAL_COMPARISON"
UNFINISHED_THREAD = "UNFINISHED_THREAD"
PERSONAL_FACT = "PERSONAL_FACT"
SUPPORTED_INFERENCE = "SUPPORTED_INFERENCE"
GENERAL_COMPANION = "GENERAL_COMPANION"
APP_IDENTITY = "APP_IDENTITY"

ALL_CATEGORIES = [
    EXACT_QUOTE,
    TEMPORAL_COMPARISON,
    UNFINISHED_THREAD,
    PERSONAL_FACT,
    SUPPORTED_INFERENCE,
    GENERAL_COMPANION,
    APP_IDENTITY,
]

# ── Rule-based patterns (deterministic, no LLM cost) ──────────────────────

# EXACT_QUOTE: "what did X say", "quote", "exact words", "verbatim"
EXACT_QUOTE_PATTERNS = [
    r"\bwhat (did|do) (you|i|he|she|they|\w+) (say|tell|write|mention)\b",
    r"\bexact(ly)? (what|words?|message)\b",
    r"\bverbatim\b",
    r"\bquote\b",
    r"\bthe (exact|original) (message|words?|text)\b",
    r"\bdid (you|i|he|she|they|\w+) (say|write|mention)\b",
    r"\bwhat were (the|your|his|her|their) (exact )?words\b",
]

# TEMPORAL_COMPARISON: "last week vs this week", "before vs after", "compare"
TEMPORAL_PATTERNS = [
    r"\b(last|this) (week|month|year|day) vs\b",
    r"\bbefore vs after\b",
    r"\bcompare (last|this|yesterday|today)\b",
    r"\bwhat changed (since|from)\b",
    r"\bhow (has|have) (it|things?) changed\b",
    r"\b(difference|differ) between\b",
    r"\b(in|during) (january|february|march|april|may|june|july|august|september|october|november|december)\b",
    r"\b\d{4}\b.*\bvs\b.*\b\d{4}\b",
    r"\b(yesterday|today|last week|last month)\b.*\bvs\b",
]

# UNFINISHED_THREAD: "you never finished", "you were saying", "continue"
UNFINISHED_PATTERNS = [
    r"\byou (never|didn'?t) (finish|complete|tell|end)\b",
    r"\byou were (saying|telling|about to)\b",
    r"\bcontinue (from|where|that)\b",
    r"\bwhere (did|were) you (leave off|stop)\b",
    r"\bwhat happened (next|after that)\b",
    r"\band then what\b",
    r"\bgo on\b",
    r"\bkeep going\b",
    r"\bwhat (else|more) (did|do) you\b",
    r"\btell me more\b",
    r"\bwhat (comes|come) next\b",
    r"\bnever finished\b",
    r"\bdidn'?t finish\b",
    r"\bnever (told|tell) me\b",
    r"\bleft off\b",
    r"\bwhere (we|you) (left off|stopped)\b",
]

# PERSONAL_FACT: "my favorite", "do I like", "what's my"
PERSONAL_FACT_PATTERNS = [
    r"\bmy (favorite|favourite|beloved|preferred)\b",
    r"\bdo i (like|love|prefer|hate|enjoy)\b",
    r"\bwhat'?s my\b",
    r"\bwhere do i\b",
    r"\bwhen (did|do|was) i\b",
    r"\bwho (am i|is my)\b",
    r"\bmy (name|birthday|hometown|job|career|family)\b",
]

# SUPPORTED_INFERENCE: "why", "what do you think", "how did I feel"
INFERENCE_PATTERNS = [
    r"\bwhy (did|do|was|were|am|is)\b",
    r"\bhow (did|do|was|were) (i|you|we|they) feel\b",
    r"\bwhat (do you think|did you think)\b",
    r"\bwhat might (have )?(happened|caused)\b",
    r"\bexplain (why|how)\b",
    r"\bwhat does (it|this) mean\b",
]

# APP_IDENTITY: "who are you", "what are you", "are you real"
APP_IDENTITY_PATTERNS = [
    r"\bwho are you\b",
    r"\bwhat are you\b",
    r"\bare you (real|human|ai|a bot)\b",
    r"\byour name\b",
    r"\bwhat can you do\b",
    r"\bwho (made|created|built) you\b",
]

# GENERAL_COMPANION: greetings, mood, casual chat
GENERAL_COMPANION_PATTERNS = [
    r"^(hi|hey|hello|yo|sup|howdy)\b",
    r"\bhow are you\b",
    r"\bhow'?s it going\b",
    r"\bgood (morning|afternoon|evening|night)\b",
    r"\btell me (a|about a) (joke|story)\b",
    r"\bwhat'?s up\b",
]


def _match_any(text: str, patterns: list[str]) -> bool:
    """Return True if any regex pattern matches the text (case-insensitive)."""
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def classify_question(question: str) -> dict:
    """
    Classify a user question into one of 7 categories.

    Returns:
      {
        "category": str,           # one of ALL_CATEGORIES
        "confidence": float,       # 0.0 - 1.0
        "matched_rules": list[str] # which rule groups matched
      }

    Strategy: deterministic rules first (fast, free). If multiple categories
    match, prefer the most specific one (EXACT_QUOTE > TEMPORAL > UNFINISHED >
    PERSONAL_FACT > INFERENCE > APP_IDENTITY > GENERAL_COMPANION).
    """
    if not question or not question.strip():
        return {"category": GENERAL_COMPANION, "confidence": 0.0, "matched_rules": []}

    q = question.strip()
    matched = []

    # Check each category in priority order
    if _match_any(q, EXACT_QUOTE_PATTERNS):
        matched.append(EXACT_QUOTE)
    if _match_any(q, TEMPORAL_PATTERNS):
        matched.append(TEMPORAL_COMPARISON)
    if _match_any(q, UNFINISHED_PATTERNS):
        matched.append(UNFINISHED_THREAD)
    if _match_any(q, PERSONAL_FACT_PATTERNS):
        matched.append(PERSONAL_FACT)
    if _match_any(q, INFERENCE_PATTERNS):
        matched.append(SUPPORTED_INFERENCE)
    if _match_any(q, APP_IDENTITY_PATTERNS):
        matched.append(APP_IDENTITY)
    if _match_any(q, GENERAL_COMPANION_PATTERNS):
        matched.append(GENERAL_COMPANION)

    if not matched:
        # No rule matched — default to SUPPORTED_INFERENCE (most common for RAG)
        return {
            "category": SUPPORTED_INFERENCE,
            "confidence": 0.3,
            "matched_rules": [],
        }

    # Priority order: most specific wins
    priority = [
        EXACT_QUOTE,
        TEMPORAL_COMPARISON,
        UNFINISHED_THREAD,
        PERSONAL_FACT,
        SUPPORTED_INFERENCE,
        APP_IDENTITY,
        GENERAL_COMPANION,
    ]
    for cat in priority:
        if cat in matched:
            confidence = 0.9 if len(matched) == 1 else 0.6
            return {
                "category": cat,
                "confidence": confidence,
                "matched_rules": matched,
            }

    return {"category": SUPPORTED_INFERENCE, "confidence": 0.3, "matched_rules": matched}


def needs_retrieval(category: str) -> bool:
    """Return True if this category requires memory retrieval."""
    return category in {
        EXACT_QUOTE,
        TEMPORAL_COMPARISON,
        UNFINISHED_THREAD,
        PERSONAL_FACT,
        SUPPORTED_INFERENCE,
    }


def needs_date_filter(category: str) -> bool:
    """Return True if this category benefits from a date-range filter."""
    return category == TEMPORAL_COMPARISON


def needs_exact_source_card(category: str) -> bool:
    """Return True if this category should display exact source cards."""
    return category in {EXACT_QUOTE, TEMPORAL_COMPARISON, PERSONAL_FACT, UNFINISHED_THREAD}
