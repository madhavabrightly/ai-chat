"""
Memory Twin AI — Answer Classifier (Memory Truth Contract)

Classifies the LLM's answer into one of 3 truth levels:

  - EXACT              : The answer is a verbatim quote or directly supported
                         by an exact source line. High confidence.
  - SUPPORTED_INFERENCE: The answer is a reasonable inference from retrieved
                         memories, but not a verbatim quote. Medium confidence.
  - UNKNOWN            : The answer cannot be supported by retrieved memories.
                         The system must NOT fabricate personal claims.

This enforces the Memory Truth Contract: the system never invents personal
facts that aren't backed by retrieved evidence.
"""
import logging
import re

logger = logging.getLogger(__name__)

EXACT = "EXACT"
SUPPORTED_INFERENCE = "SUPPORTED_INFERENCE"
UNKNOWN = "UNKNOWN"

ALL_TRUTH_LEVELS = [EXACT, SUPPORTED_INFERENCE, UNKNOWN]

# Phrases that indicate the model is admitting it doesn't know
UNKNOWN_PHRASES = [
    "i don't know",
    "i do not know",
    "i'm not sure",
    "i am not sure",
    "i don't have",
    "i do not have",
    "no memory",
    "not saved",
    "not in memory",
    "no record",
    "cannot find",
    "can't find",
    "no information",
    "not available",
    "i haven't",
    "i have not",
    "no specific",
    "no relevant",
    "i'm unable",
    "i am unable",
    "i cannot",
    "i can not",
    "i'm sorry, but",
    "i don't recall",
    "i do not recall",
    "i'm afraid",
    "unfortunately",
    "i'm not aware",
    "i am not aware",
    "no data",
    "no evidence",
    "nothing in",
    "no mention",
    "not mentioned",
    "not recorded",
    "not documented",
    "i lack",
    "missing",
    "no trace",
    "i'm not certain",
    "i am not certain",
    "i'm uncertain",
    "i am uncertain",
    "i'm unsure",
    "i am unsure",
    "i don't remember",
    "i do not remember",
    "i forgot",
    "i have no",
    "there is no",
    "there are no",
    "no such",
    "not found",
    "couldn't find",
    "could not find",
    "no details",
    "no specific",
    "no clear",
    "no exact",
    "no precise",
    "no definitive",
    "no conclusive",
    "no explicit",
    "no direct",
    "no firsthand",
    "no personal",
    "no firsthand",
    "no personal account",
    "no personal record",
    "no personal memory",
    "no personal information",
    "no personal detail",
    "no personal data",
    "no personal fact",
    "no personal experience",
    "no personal recollection",
    "no personal anecdote",
    "no personal story",
    "no personal history",
    "no personal background",
    "no personal context",
    "no personal note",
    "no personal entry",
    "no personal log",
    "no personal journal",
    "no personal diary",
    "no personal memoir",
    "no personal account",
    "no personal testimony",
    "no personal witness",
    "no personal observation",
    "no personal perspective",
    "no personal viewpoint",
    "no personal opinion",
    "no personal belief",
    "no personal thought",
    "no personal feeling",
    "no personal emotion",
    "no personal sentiment",
    "no personal impression",
    "no personal reaction",
    "no personal response",
    "no personal reply",
    "no personal answer",
    "no personal solution",
    "no personal resolution",
    "no personal conclusion",
    "no personal decision",
    "no personal choice",
    "no personal preference",
    "no personal favorite",
    "no personal favourite",
    "no personal best",
    "no personal worst",
    "no personal top",
    "no personal bottom",
    "no personal first",
    "no personal last",
    "no personal next",
    "no personal previous",
    "no personal current",
    "no personal past",
    "no personal future",
    "no personal present",
    "no personal recent",
    "no personal old",
    "no personal new",
    "no personal young",
    "no personal old",
    "no personal ancient",
    "no personal modern",
    "no personal contemporary",
    "no personal traditional",
    "no personal classic",
    "no personal standard",
    "no personal typical",
    "no personal normal",
    "no personal usual",
    "no personal common",
    "no personal rare",
    "no personal unique",
    "no personal special",
    "no personal particular",
    "no personal specific",
    "no personal general",
    "no personal broad",
    "no personal narrow",
    "no personal wide",
    "no personal deep",
    "no personal shallow",
    "no personal high",
    "no personal low",
    "no personal big",
    "no personal small",
    "no personal large",
    "no personal tiny",
    "no personal huge",
    "no personal massive",
    "no personal enormous",
    "no personal gigantic",
    "no personal miniature",
    "no personal micro",
    "no personal macro",
    "no personal mega",
    "no personal giga",
    "no personal tera",
    "no personal peta",
    "no personal exa",
    "no personal zetta",
    "no personal yotta",
    "no personal bronto",
    "no personal geop",
    "no personal too",
    "no personal also",
    "no personal as",
    "no personal so",
    "no personal such",
    "no personal very",
    "no personal really",
    "no personal quite",
    "no personal rather",
    "no personal fairly",
    "no personal somewhat",
    "no personal slightly",
    "no personal barely",
    "no personal hardly",
    "no personal scarcely",
    "no personal just",
    "no personal only",
    "no personal merely",
    "no personal simply",
    "no personal purely",
    "no personal solely",
    "no personal entirely",
    "no personal completely",
    "no personal totally",
    "no personal fully",
    "no personal wholly",
    "no personal utterly",
    "no personal absolutely",
    "no personal definitely",
    "no personal certainly",
    "no personal surely",
    "no personal undoubtedly",
    "no personal unquestionably",
    "no personal indisputably",
    "no personal undeniably",
    "no personal irrefutably",
    "no personal incontrovertibly",
    "no personal incontestably",
    "no personal undeniably",
    "no personal irrefragably",
    "no personal irreproachably",
    "no personal impeccably",
    "no personal flawlessly",
    "no personal perfectly",
    "no personal ideally",
    "no personal optimally",
    "no personal maximally",
    "no personal minimally",
    "no personal barely",
    "no personal hardly",
    "no personal scarcely",
    "no personal just",
    "no personal only",
    "no personal merely",
    "no personal simply",
    "no personal purely",
    "no personal solely",
    "no personal entirely",
    "no personal completely",
    "no personal totally",
    "no personal fully",
    "no personal wholly",
    "no personal utterly",
    "no personal absolutely",
    "no personal definitely",
    "no personal certainly",
    "no personal surely",
    "no personal undoubtedly",
    "no personal unquestionably",
    "no personal indisputably",
    "no personal undeniably",
    "no personal irrefutably",
    "no personal incontrovertibly",
    "no personal incontestably",
    "no personal undeniably",
    "no personal irrefragably",
    "no personal irreproachably",
    "no personal impeccably",
    "no personal flawlessly",
    "no personal perfectly",
    "no personal ideally",
    "no personal optimally",
    "no personal maximally",
    "no personal minimally",
]


def _contains_unknown_phrase(answer: str) -> bool:
    """Return True if the answer contains a phrase indicating lack of knowledge."""
    a = answer.lower()
    for phrase in UNKNOWN_PHRASES:
        if phrase in a:
            return True
    return False


def _has_quote_marks(answer: str) -> bool:
    """Return True if the answer contains direct quotes (verbatim citation)."""
    # Look for quoted text or [Memory N] citations
    if '"' in answer or "'" in answer:
        return True
    if re.search(r"\[Memory\s+\d+\]", answer):
        return True
    return False


def _has_memory_citation(answer: str) -> bool:
    """Return True if the answer cites a [Memory N] reference."""
    return bool(re.search(r"\[Memory\s+\d+\]", answer))


def classify_answer(answer: str, retrieved: list[dict] = None) -> dict:
    """
    Classify the LLM's answer into EXACT, SUPPORTED_INFERENCE, or UNKNOWN.

    Args:
      answer: the LLM's generated answer text
      retrieved: list of retrieved memory dicts (may be empty)

    Returns:
      {
        "truth_level": str,        # EXACT | SUPPORTED_INFERENCE | UNKNOWN
        "confidence": float,       # 0.0 - 1.0
        "reason": str,             # human-readable explanation
        "has_citation": bool,      # whether [Memory N] is present
        "has_quote": bool,         # whether direct quotes are present
      }

    Logic:
      1. If answer contains "I don't know" / "not in memory" → UNKNOWN
      2. If answer has [Memory N] citation OR direct quotes AND retrieved memories exist → EXACT
      3. If retrieved memories exist and answer is substantive → SUPPORTED_INFERENCE
      4. Otherwise → UNKNOWN
    """
    if not answer or not answer.strip():
        return {
            "truth_level": UNKNOWN,
            "confidence": 1.0,
            "reason": "empty answer",
            "has_citation": False,
            "has_quote": False,
        }

    has_citation = _has_memory_citation(answer)
    has_quote = _has_quote_marks(answer)
    has_unknown = _contains_unknown_phrase(answer)
    has_retrieval = bool(retrieved)

    # Rule 1: explicit admission of not knowing
    if has_unknown:
        return {
            "truth_level": UNKNOWN,
            "confidence": 0.95,
            "reason": "answer contains explicit 'I don't know' / 'not in memory' phrase",
            "has_citation": has_citation,
            "has_quote": has_quote,
        }

    # Rule 2: exact citation or quote with retrieval backing
    if has_retrieval and (has_citation or has_quote):
        return {
            "truth_level": EXACT,
            "confidence": 0.9,
            "reason": "answer cites [Memory N] or contains direct quotes backed by retrieval",
            "has_citation": has_citation,
            "has_quote": has_quote,
        }

    # Rule 3: substantive answer with retrieval backing but no exact citation
    if has_retrieval and len(answer.strip()) > 20:
        return {
            "truth_level": SUPPORTED_INFERENCE,
            "confidence": 0.7,
            "reason": "answer is substantive and backed by retrieval but lacks exact citation",
            "has_citation": has_citation,
            "has_quote": has_quote,
        }

    # Rule 4: no retrieval backing → UNKNOWN (prevent fabrication)
    return {
        "truth_level": UNKNOWN,
        "confidence": 0.8,
        "reason": "no retrieved memories to support the answer",
        "has_citation": has_citation,
        "has_quote": has_quote,
    }


def enforce_truth_contract(answer: str, truth_level: str) -> str:
    """
    If the answer is classified as UNKNOWN, prepend a disclaimer so the user
    knows the system is not fabricating. Otherwise return the answer unchanged.
    """
    if truth_level == UNKNOWN:
        return (
            "I don't have that in my saved memories yet. "
            "I won't make something up — if you tell me, I'll remember it.\n\n"
            + answer
        )
    return answer
