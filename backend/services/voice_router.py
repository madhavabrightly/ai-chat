"""
Memory Twin AI — Voice Router

Routes text to appropriate voice synthesis based on companion type and mood.
Preference order: CosyVoice2 (v2) → CosyVoice (v1) → browser TTS fallback.
"""
import logging
from backend.models.tts_loader import synthesize_speech, get_tts
from backend.services.tts_service import generate_tts, tts2_model
from backend.services.companion_profile import get_voice_settings

logger = logging.getLogger(__name__)


def generate_companion_voice(text: str, companion_type: str = "female", mood: str = "calm") -> dict:
    """
    Generate companion voice audio.

    1. Get voice settings (pitch, rate) based on companion type + mood.
    2. Try CosyVoice2 (v2 — emotion-aware instruct mode).
    3. Fall back to CosyVoice (v1).
    4. If both unavailable, return fallback signal for browser TTS.

    Returns:
        On success: {"audio_url": "...", "voice_profile": "...", "companion_type": "...", "mood": "..."}
        On fallback: {"fallback": "browser_tts", "voice_settings": {...}}
    """
    settings = get_voice_settings(companion_type, mood)

    # Try CosyVoice2 (v2) first — emotion-aware
    if tts2_model is not None:
        result = generate_tts(text, companion_type, mood)
        if "audio_url" in result:
            return {
                "audio_url": result["audio_url"],
                "voice_profile": settings["voice_profile"],
                "companion_type": companion_type,
                "mood": mood,
            }

    # Fall back to CosyVoice (v1)
    if get_tts() is not None:
        result = synthesize_speech(text, companion_type, mood)
        if "audio_url" in result:
            return {
                "audio_url": result["audio_url"],
                "voice_profile": settings["voice_profile"],
                "companion_type": companion_type,
                "mood": mood,
            }

    # Final fallback to browser TTS
    return {
        "fallback": "browser_tts",
        "voice_settings": settings,
        "companion_type": companion_type,
        "mood": mood,
    }
