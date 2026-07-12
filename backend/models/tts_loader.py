"""
Memory Twin AI — Text-to-Speech Loader (CosyVoice-300M, v1)

Generates synthetic speech for the selected companion.
Falls back gracefully if model is unavailable. The v2 (CosyVoice2) path
lives in services/tts_service.py and is preferred when available.
"""
import logging
import os
import uuid
import torch
import torchaudio
from backend.config import TTS_MODEL_ID, GENERATED_AUDIO_DIR, FORCE_CPU
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
    Generate synthetic speech for companion voice using CosyVoice v1.

    Uses inference_sft with a built-in speaker if available, otherwise
    falls back to browser TTS.
    """
    if tts_model is None:
        return {"fallback": "browser_tts", "reason": "TTS model not loaded"}

    if not text or not text.strip():
        return {"fallback": "browser_tts", "reason": "empty text"}

    try:
        # List available built-in speakers
        speakers = tts_model.list_available_spks() if hasattr(tts_model, "list_available_spks") else []
        # Pick a speaker based on companion type (best-effort)
        speaker = None
        if speakers:
            # Prefer female/male-named speakers if available
            for s in speakers:
                if companion_type == "female" and "female" in s.lower():
                    speaker = s
                    break
                if companion_type == "male" and "male" in s.lower():
                    speaker = s
                    break
            if speaker is None:
                speaker = speakers[0]

        if speaker:
            outputs = list(tts_model.inference_sft(text, speaker, stream=False))
        else:
            # No built-in speaker — use zero-shot with a default prompt
            outputs = list(tts_model.inference_cross_lingual(text, stream=False))

        if not outputs:
            return {"fallback": "browser_tts", "reason": "no audio generated"}

        tts_speech = outputs[0]["tts_speech"]
        sample_rate = tts_model.sample_rate

        os.makedirs(GENERATED_AUDIO_DIR, exist_ok=True)
        audio_id = uuid.uuid4().hex[:12]
        audio_path = os.path.join(GENERATED_AUDIO_DIR, f"tts_{audio_id}.wav")
        torchaudio.save(audio_path, tts_speech.cpu(), sample_rate)

        return {
            "audio_url": f"/audio/tts_{audio_id}.wav",
            "voice_profile": f"{companion_type}_adult_warm",
            "sample_rate": sample_rate,
            "fallback": False,
        }
    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}")
        return {"fallback": "browser_tts", "reason": str(e)}
