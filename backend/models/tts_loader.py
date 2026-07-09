"""
Memory Twin AI — Text-to-Speech Loader (CosyVoice-300M)

Generates synthetic speech for the selected companion.
Supports male/female voice profiles.
Falls back gracefully if model is unavailable.
"""
import logging
import os
from backend.config import TTS_MODEL_ID
from backend.models.model_registry import get_model_path

logger = logging.getLogger(__name__)

# Global singleton
tts_model = None


def load_tts():
    """Load CosyVoice TTS model once at startup."""
    global tts_model
    local_path = get_model_path("tts")

    if not os.path.isdir(local_path):
        logger.warning(f"TTS model not found locally at {local_path}. TTS will use browser fallback.")
        return None

    try:
        from cosyvoice.cli.cosyvoice import CosyVoice
        logger.info(f"Loading TTS: {TTS_MODEL_ID}")
        tts_model = CosyVoice(local_path)
        logger.info("TTS loaded successfully.")
        return tts_model
    except Exception as e:
        logger.warning(f"TTS model load failed: {e}. Using browser TTS fallback.")
        tts_model = None
        return None


def get_tts():
    """Return loaded TTS model or None."""
    return tts_model


def synthesize_speech(text: str, companion_type: str = "female", mood: str = "calm") -> dict:
    """
    Generate synthetic speech for companion voice.

    Returns dict with audio_url or fallback signal.
    """
    if tts_model is None:
        return {"fallback": "browser_tts", "reason": "TTS model not loaded"}

    try:
        # CosyVoice inference — adjust voice based on companion type
        # For now this is a stub that returns fallback
        # Full implementation would:
        #   1. Select speaker embedding (male_adult / female_adult)
        #   2. Adjust inference params based on mood
        #   3. Save audio to GENERATED_AUDIO_DIR
        #   4. Return audio URL

        return {"fallback": "browser_tts", "reason": "model loaded but inference stub"}
    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}")
        return {"fallback": "browser_tts", "reason": str(e)}
