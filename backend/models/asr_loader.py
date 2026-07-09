"""
Memory Twin AI — Speech-to-Text Loader (SenseVoiceSmall)

Converts user voice input to text.
Falls back gracefully if model is unavailable.
"""
import logging
import os
from backend.config import ASR_MODEL_ID
from backend.models.model_registry import get_model_path

logger = logging.getLogger(__name__)

# Global singleton
asr_model = None
asr_processor = None


def load_asr():
    """Load SenseVoice ASR model once at startup."""
    global asr_model, asr_processor
    local_path = get_model_path("asr")

    if not os.path.isdir(local_path):
        logger.warning(f"ASR model not found locally at {local_path}. ASR will use browser fallback.")
        return None

    try:
        from funasr import AutoModel
        logger.info(f"Loading ASR: {ASR_MODEL_ID}")
        asr_model = AutoModel(
            model=local_path,
            vad_model="fsmn-vad",
            punc_model="ct-punc",
            disable_update=True,
        )
        logger.info("ASR loaded successfully.")
        return asr_model
    except Exception as e:
        logger.warning(f"ASR model load failed: {e}. Using browser SpeechRecognition fallback.")
        asr_model = None
        return None


def get_asr():
    """Return loaded ASR model or None."""
    return asr_model


def transcribe_audio(audio_path: str) -> dict:
    """
    Transcribe audio file to text.

    Returns dict with text or fallback signal.
    """
    if asr_model is None:
        return {"fallback": "browser_asr", "reason": "ASR model not loaded"}

    try:
        result = asr_model.generate(input=audio_path)
        text = result[0]["text"] if result else ""
        return {"text": text}
    except Exception as e:
        logger.error(f"ASR transcription failed: {e}")
        return {"fallback": "browser_asr", "reason": str(e)}
