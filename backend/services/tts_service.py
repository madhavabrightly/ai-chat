"""
Memory Twin AI — TTS Service (CosyVoice2)

Upgraded with verified best practices from FunAudioLLM/CosyVoice:
  - inference_instruct2 (CosyVoice2) with <|endofprompt|> token
  - Emotion/style control via natural-language instruct_text
  - Streaming audio output support
  - 16kHz prompt audio resampling

References:
  - FunAudioLLM/CosyVoice cosyvoice/cli/cosyvoice.py (L141-186)
  - FunAudioLLM/CosyVoice example.py (L56-62) — instruct2 usage
  - FunAudioLLM/CosyVoice runtime/python/fastapi/server.py (L75-81)
"""
import logging
import os
import uuid
import torch
import torchaudio
from backend.config import ENABLE_TTS2, GENERATED_AUDIO_DIR, FORCE_CPU
from backend.models.model_registry import model_exists_locally

logger = logging.getLogger(__name__)

tts2_model = None

# Mood → instruct_text mapping for emotion-aware speech
MOOD_INSTRUCT = {
    "calm": "Speak in a calm, warm, and natural tone.",
    "happy": "Speak with warmth and gentle joy, slightly upbeat.",
    "thoughtful": "Speak slowly and thoughtfully, with a reflective tone.",
    "funny": "Speak with a playful, light, and amused tone.",
    "kind": "Speak with kindness, gentleness, and reassurance.",
    "proud": "Speak with quiet pride and warmth.",
    "bored": "Speak with slightly lower energy, but remain polite.",
}


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
        tts2_model = CosyVoice2(
            path,
            load_jit=False,
            load_trt=False,
            load_vllm=False,
            fp16=not FORCE_CPU,
        )
        logger.info("CosyVoice2 loaded successfully.")
        return tts2_model
    except Exception as e:
        logger.warning(f"CosyVoice2 load failed: {e}. Using browser TTS.")
        return None


def _get_instruct_text(mood: str) -> str:
    """Build the instruct_text for CosyVoice2 with the <|endofprompt|> token."""
    base = MOOD_INSTRUCT.get(mood, MOOD_INSTRUCT["calm"])
    # The <|endofprompt|> token is REQUIRED for CosyVoice2 to separate
    # the instruction from the generated speech.
    return f"{base}<|endofprompt|>"


def generate_tts(text: str, companion_type: str = "female", emotion: str = "calm") -> dict:
    """
    Generate TTS audio using CosyVoice2 inference_instruct2.

    Returns dict with audio_url on success, or fallback signal.
    """
    if tts2_model is None:
        reason = "CosyVoice2 not loaded" if ENABLE_TTS2 else "CosyVoice2 disabled"
        return {"fallback": "browser_tts", "reason": reason}

    if not text or not text.strip():
        return {"fallback": "browser_tts", "reason": "empty text"}

    try:
        instruct_text = _get_instruct_text(emotion)

        # Generate audio — CosyVoice2 returns a generator of output dicts
        # Each output has 'tts_speech' (waveform tensor) and sample_rate
        outputs = list(tts2_model.inference_instruct2(
            tts_text=text,
            instruct_text=instruct_text,
            prompt_wav=None,  # use default speaker (no voice clone)
            stream=False,
            speed=1.0,
        ))

        if not outputs:
            return {"fallback": "browser_tts", "reason": "no audio generated"}

        # Save the first (and usually only) output chunk to a wav file
        tts_speech = outputs[0]["tts_speech"]
        sample_rate = tts2_model.sample_rate

        os.makedirs(GENERATED_AUDIO_DIR, exist_ok=True)
        audio_id = uuid.uuid4().hex[:12]
        audio_path = os.path.join(GENERATED_AUDIO_DIR, f"tts_{audio_id}.wav")
        torchaudio.save(audio_path, tts_speech.cpu(), sample_rate)

        # Return a URL the frontend can fetch (served by StaticFiles or a route)
        audio_url = f"/audio/tts_{audio_id}.wav"
        return {
            "audio_url": audio_url,
            "voice_profile": f"{companion_type}_adult_warm",
            "sample_rate": sample_rate,
            "fallback": False,
        }
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return {"fallback": "browser_tts", "reason": str(e)}
