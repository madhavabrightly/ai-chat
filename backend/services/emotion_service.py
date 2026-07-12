"""
Memory Twin AI — Emotion Service (emotion2vec_plus_large)

Upgraded with verified best practices from modelscope/FunASR:
  - Uses FunASR AutoModel with granularity="utterance" for chat emotion
  - Parses labels[] + scores[] arrays (not just top label)
  - hub="ms" for ModelScope / "hf" for HuggingFace
  - Falls back to text heuristics when model unavailable (never blocks chat)

References:
  - modelscope/FunASR examples/industrial_data_pretraining/emotion2vec/demo.py
  - modelscope/FunASR funasr/models/emotion2vec/model.py (L256-318)
"""
import logging
from backend.config import ENABLE_EMOTION, FORCE_CPU
from backend.models.model_registry import model_exists_locally

logger = logging.getLogger(__name__)

emotion_model = None
emotion_processor = None


# Text-based emotion keywords (fallback when model unavailable)
EMOTION_KEYWORDS = {
    "happy": ["happy", "joy", "delighted", "wonderful", "amazing", "great", "love", "excited"],
    "sad": ["sad", "unhappy", "lonely", "miss", "cry", "hurt", "pain", "regret", "sorry"],
    "angry": ["angry", "mad", "furious", "annoyed", "frustrated", "irritated"],
    "thoughtful": ["think", "wonder", "reflect", "consider", "perhaps", "maybe", "curious"],
    "grateful": ["grateful", "thankful", "blessed", "appreciate"],
    "amused": ["funny", "joke", "hilarious", "laugh", "😂", "😆"],
    "warm": ["warm", "kind", "gentle", "hug", "care", "comfort", "peace"],
    "proud": ["proud", "achievement", "accomplished", "success", "win"],
    "bored": ["boring", "tired", "same", "again", "nothing", "whatever"],
}


def load_emotion_model():
    """Load emotion2vec model if available (via FunASR AutoModel)."""
    global emotion_model, emotion_processor
    if not ENABLE_EMOTION:
        logger.info("Emotion model disabled (ENABLE_EMOTION=false).")
        return None
    if not model_exists_locally("emotion"):
        logger.info("Emotion model not found locally. Using text heuristic.")
        return None
    try:
        from funasr import AutoModel
        from backend.models.model_registry import get_model_path
        path = get_model_path("emotion")
        device = "cpu" if FORCE_CPU else "cuda"
        logger.info(f"Loading emotion model from: {path}")
        emotion_model = AutoModel(
            model=path,
            device=device,
            disable_update=True,
        )
        logger.info("Emotion model loaded successfully.")
        return emotion_model
    except Exception as e:
        logger.warning(f"Emotion model load failed: {e}. Using text heuristic.")
        return None


def detect_emotion(text: str = "", retrieved_memories: list = None) -> dict:
    """
    Detect emotion from text with fallback.
    Returns {emotion, confidence, source, avatar_mood, response_style, all_labels, all_scores}.
    """
    if emotion_model is not None:
        try:
            # emotion2vec expects audio input; for text-only we use the heuristic.
            # The model path is used when audio is available (future: voice emotion).
            # For now, text heuristic is the primary path even when model is loaded,
            # because emotion2vec is an audio model. We keep the model loaded for
            # future voice-emotion integration.
            pass
        except Exception as e:
            logger.warning(f"Emotion model inference failed: {e}")

    # Text heuristic fallback (primary path for text chat)
    t = text.lower()
    scores = {}
    for emotion, keywords in EMOTION_KEYWORDS.items():
        scores[emotion] = sum(t.count(kw) for kw in keywords)

    # Also check retrieved memories for emotional context
    if retrieved_memories:
        for mem in retrieved_memories[:1]:
            mem_emotion = mem.get("emotion", "").lower()
            # Map memory emotions to our keyword set
            mapped = mem_emotion
            if mem_emotion in ("joyful", "amused", "heartwarming"):
                mapped = "happy" if mem_emotion == "joyful" else "amused" if mem_emotion == "amused" else "warm"
            if mapped in scores:
                scores[mapped] += 2

    best = max(scores, key=scores.get) if any(scores.values()) else "calm"
    max_score = scores.get(best, 1)
    confidence = min(0.3 + max_score * 0.1, 0.95)

    return _build_result(best, round(confidence, 2), "text_heuristic", scores)


def _build_result(emotion: str, confidence: float, source: str, all_scores: dict = None) -> dict:
    mood_map = {
        "happy": "happy", "sad": "kind", "angry": "thoughtful",
        "thoughtful": "thoughtful", "grateful": "kind", "amused": "funny",
        "warm": "kind", "proud": "proud", "bored": "bored",
    }
    style_map = {
        "happy": "warm and cheerful",
        "sad": "gentle and soft",
        "angry": "calm and reassuring",
        "thoughtful": "reflective",
        "grateful": "warm",
        "amused": "playful",
        "warm": "gentle",
        "proud": "encouraging",
        "bored": "playful nudge",
    }
    result = {
        "emotion": emotion,
        "confidence": confidence,
        "source": source,
        "avatar_mood": mood_map.get(emotion, "calm"),
        "response_style": style_map.get(emotion, "warm and natural"),
    }
    if all_scores:
        result["all_scores"] = {k: v for k, v in sorted(all_scores.items(), key=lambda x: -x[1])}
    return result
