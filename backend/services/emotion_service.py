"""
Memory Twin AI — Emotion Service

Detects emotion from text (and optionally audio).
Uses emotion2vec when available, otherwise falls back to text heuristics.
Never blocks chat. Never crashes.
"""
import logging
from backend.config import ENABLE_EMOTION
from backend.models.model_registry import model_exists_locally

logger = logging.getLogger(__name__)

emotion_model = None
emotion_processor = None


# Text-based emotion keywords
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
    """Load emotion2vec model if available."""
    global emotion_model, emotion_processor
    if not ENABLE_EMOTION:
        logger.info("Emotion model disabled (ENABLE_EMOTION=false).")
        return None
    if not model_exists_locally("emotion"):
        logger.info("Emotion model not found locally. Using text heuristic.")
        return None
    try:
        from modelscope.pipelines import pipeline
        from backend.models.model_registry import get_model_path
        path = get_model_path("emotion")
        logger.info(f"Loading emotion model from: {path}")
        emotion_model = pipeline("emotion", model=path, device="cuda:0")
        logger.info("Emotion model loaded successfully.")
        return emotion_model
    except Exception as e:
        logger.warning(f"Emotion model load failed: {e}. Using text heuristic.")
        return None


def detect_emotion(text: str = "", retrieved_memories: list = None) -> dict:
    """
    Detect emotion from text with fallback.
    Returns {emotion, confidence, source, avatar_mood, response_style}.
    """
    if emotion_model is not None:
        try:
            result = emotion_model(text)
            emotion = result.get("label", "calm") if result else "calm"
            confidence = result.get("score", 0.0) if result else 0.0
            return _build_result(emotion, confidence, "audio_model")
        except Exception as e:
            logger.warning(f"Emotion model inference failed: {e}")

    # Text heuristic fallback
    t = text.lower()
    scores = {}
    for emotion, keywords in EMOTION_KEYWORDS.items():
        scores[emotion] = sum(t.count(kw) for kw in keywords)

    # Also check retrieved memories for emotional context
    if retrieved_memories:
        for mem in retrieved_memories[:1]:
            mem_emotion = mem.get("emotion", "").lower()
            if mem_emotion in scores:
                scores[mem_emotion] += 2

    best = max(scores, key=scores.get) if any(scores.values()) else "calm"
    max_score = scores.get(best, 1)
    confidence = min(0.3 + max_score * 0.1, 0.95)

    return _build_result(best, round(confidence, 2), "text_heuristic")


def _build_result(emotion: str, confidence: float, source: str) -> dict:
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
    return {
        "emotion": emotion,
        "confidence": confidence,
        "source": source,
        "avatar_mood": mood_map.get(emotion, "calm"),
        "response_style": style_map.get(emotion, "warm and natural"),
    }
