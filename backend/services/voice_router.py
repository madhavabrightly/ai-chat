"""
Memory Twin AI — Voice Router

Routes text to appropriate voice synthesis based on companion type and mood.
Falls back to browser TTS if backend TTS model is unavailable.
"""
import logging
from backend.models.tts_loader import synthesize_speech, get_tts
from backend.services.companion_profile import get_voice_settings

logger = logging.getLogger(__name__)


def generate_companion_voice(text: str, companion_type: str = "female", mood: str = "calm") -> dict:
    """
    Generate companion voice audio.

    1. Get voice settings (pitch, rate) based on companion type + mood.
    2. Try backend TTS model (CosyVoice).
    3. If unavailable, return fallback signal for browser TTS.

    Returns:
        On success: {"audio_url": "...", "voice_profile": "...", "companion_type": "...", "mood": "..."}
        On fallback: {"fallback": "browser_tts", "voice_settings": {...}}
    """
    settings = get_voice_settings(companion_type, mood)

    # Try backend TTS
    if get_tts() is not None:
        result = synthesize_speech(text, companion_type, mood)
        if "audio_url" in result:
            return {
                "audio_url": result["audio_url"],
                "voice_profile": settings["voice_profile"],
                "companion_type": companion_type,
                "mood": mood,
            }

    # Fallback to browser TTS
    return {
        "fallback": "browser_tts",
        "voice_settings": settings,
        "companion_type": companion_type,
        "mood": mood,
    }
