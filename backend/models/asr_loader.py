"""
Memory Twin AI — Speech-to-Text Loader (SenseVoiceSmall)

Upgraded with verified best practices from modelscope/FunASR:
  - rich_transcription_postprocess to strip internal tags (<|zh|>, <|HAPPY|>, etc.)
  - language="auto", use_itn=True, merge_vad=True, merge_length_s=15
  - vad_kwargs with max_single_segment_time=30000 (30s)
  - disable_update=True (skip network check on startup)

References:
  - modelscope/FunASR examples/industrial_data_pretraining/sense_voice/demo.py
  - modelscope/FunASR tests_models/test_sensevoice.py (L6-32)
"""
import logging
import os
from backend.config import ASR_MODEL_ID, FORCE_CPU
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
        device = "cpu" if FORCE_CPU else "cuda:0"
        asr_model = AutoModel(
            model=local_path,
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},  # 30s max segment
            device=device,
            disable_update=True,  # skip update check (faster startup)
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

    Uses rich_transcription_postprocess to strip SenseVoice's internal tags
    (<|zh|>, <|HAPPY|>, <|woitn|>, etc.) that would otherwise leak into chat.
    """
    if asr_model is None:
        return {"fallback": "browser_asr", "reason": "ASR model not loaded"}

    try:
        res = asr_model.generate(
            input=audio_path,
            cache={},
            language="auto",        # auto-detect: zh, en, yue, ja, ko
            use_itn=True,           # inverse text normalization (numbers, dates)
            batch_size_s=60,        # batch by 60s of audio
            merge_vad=True,         # merge VAD segments
            merge_length_s=15,      # merge up to 15s segments
        )
        raw_text = res[0]["text"] if res else ""

        # Strip internal tags via the official postprocessor
        try:
            from funasr.utils.postprocess_utils import rich_transcription_postprocess
            text = rich_transcription_postprocess(raw_text)
        except ImportError:
            # Fallback: strip tags with regex if postprocess utils unavailable
            import re
            text = re.sub(r"<\|[^|]+\|>", "", raw_text).strip()

        return {"text": text}
    except Exception as e:
        logger.error(f"ASR transcription failed: {e}")
        return {"fallback": "browser_asr", "reason": str(e)}
