"""
Memory Twin AI — Language Guard

Detects non-English text in model responses.
If Chinese characters are found, attempts regeneration with stronger English-only prompt.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Chinese Unicode range
CHINESE_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')

# Tamil, Hindi, other scripts (basic ranges)
NON_ENGLISH_RE = re.compile(r'[\u0900-\u0dff\u0e00-\u0e7f\u0600-\u06ff]')


def contains_non_english(text: str) -> bool:
    """Check if text contains non-English characters."""
    if not text:
        return False
    return bool(CHINESE_RE.search(text) or NON_ENGLISH_RE.search(text))


def clean_to_english(text: str, regenerate_fn=None) -> str:
    """
    Check and clean response to English.
    If contains non-English chars, try regeneration or strip.
    """
    if not contains_non_english(text):
        return text

    logger.warning(f"[LANGUAGE_GUARD] non_english_detected=true in: {text[:80]}...")

    # Try regeneration if callback provided
    if regenerate_fn:
        try:
            regenerated = regenerate_fn()
            if regenerated and not contains_non_english(regenerated):
                logger.info("[LANGUAGE_GUARD] regeneration successful")
                return regenerated
        except Exception as e:
            logger.warning(f"[LANGUAGE_GUARD] regeneration failed: {e}")

    # Fallback: strip non-English characters
    cleaned = CHINESE_RE.sub('', text)
    cleaned = NON_ENGLISH_RE.sub('', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if cleaned and len(cleaned) > 10:
        logger.info("[LANGUAGE_GUARD] cleaned by removing non-English characters")
        return cleaned

    # Last resort
    logger.warning("[LANGUAGE_GUARD] returning English-only fallback message")
    return "I found a memory, but the response mixed languages. Please ask again and I will answer in English."
