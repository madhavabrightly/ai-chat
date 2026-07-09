"""
Memory Twin AI — TTS Service

Uses CosyVoice2 when available, otherwise browser TTS fallback.
Never blocks chat.
"""
import logging
import os
from backend.config import ENABLE_TTS2
from backend.models.model_registry import model_exists_locally

logger = logging.getLogger(__name__)

tts2_model = None


def load_tts2():
    """Load CosyVoice2 model if available."""
    global tts2_model
    if not ENABLE_TTS2:
        logger.info("CosyVoice2 disabled (ENABLE_TTS2=false).")
        return None
    if not model_exists_locally("tts2"):
        logger.info("CosyVoice2 model not found locally. Using browser TTS.")
        return None
    try:
        from cosyvoice.cli.cosyvoice import CosyVoice2
        from backend.models.model_registry import get_model_path
        path = get_model_path("tts2")
        logger.info(f"Loading CosyVoice2 from: {path}")
        tts2_model = CosyVoice2(path)
        logger.info("CosyVoice2 loaded successfully.")
        return tts2_model
    except Exception as e:
        logger.warning(f"CosyVoice2 load failed: {e}. Using browser TTS.")
        return None


def generate_tts(text: str, companion_type: str = "female", emotion: str = "calm") -> dict:
    """
    Generate TTS audio.
    Returns dict with audio_url or fallback signal.
    """
    if tts2_model is None:
        return {"fallback": "browser_tts", "reason": "CosyVoice2 not loaded"} if ENABLE_TTS2 else {"fallback": "browser_tts", "reason": "CosyVoice2 disabled"}

    try:
        # CosyVoice2 inference stub — real impl would generate wav file
        return {"fallback": "browser_tts", "reason": "model loaded, inference stub"}
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return {"fallback": "browser_tts", "reason": str(e)}
