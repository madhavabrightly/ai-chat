"""
Memory Twin AI — Avatar Director

Converts chat answer + retrieved memories into avatar action instructions.
The frontend uses these instructions to drive the lightweight live animation.
"""
import json
import logging
import re
import time

logger = logging.getLogger(__name__)

ALLOWED_ACTIONS = {
    "mood": {"calm", "happy", "thoughtful", "funny", "kind", "proud", "bored"},
    "expression": {
        "gentle_smile", "bright_smile", "soft_frown", "grin",
        "warm_smile", "confident_smile", "gentle_yawn",
    },
    "gesture": {
        "hands_relaxed", "hands_open", "hand_chin", "hand_wave",
        "hand_heart", "hands_chest", "head_tilt", "attentive",
    },
    "movement": {
        "still", "gentle_bounce", "slow_turn", "lean_forward",
        "lean_in", "stand_tall", "slouch", "listening",
    },
    "mouth_style": {"normal", "excited", "slow"},
    "camera": {"medium", "close", "idle"},
}

ACTION_DIRECTOR_SYSTEM_PROMPT = """You direct a real-time anime GLB avatar.
Return exactly one compact JSON object and no markdown or explanation.
Choose only from these values:
mood: calm, happy, thoughtful, funny, kind, proud, bored
expression: gentle_smile, bright_smile, soft_frown, grin, warm_smile, confident_smile, gentle_yawn
gesture: hands_relaxed, hands_open, hand_chin, hand_wave, hand_heart, hands_chest, head_tilt, attentive
movement: still, gentle_bounce, slow_turn, lean_forward, lean_in, stand_tall, slouch, listening
mouth_style: normal, excited, slow
camera: medium, close, idle
Use subtle natural motion. Never invent bone names, animation names, dialogue, or extra keys."""

MOOD_CATEGORY_MAP = {
    "Humor": "funny",
    "Career": "proud",
    "Advice": "thoughtful",
    "Faith & Kindness": "kind",
    "Childhood": "happy",
    "Family": "happy",
}


def detect_mood_from_memories(retrieved_memories: list) -> str:
    """Detect avatar mood from retrieved memory categories."""
    if not retrieved_memories or len(retrieved_memories) == 0:
        return "calm"
    top_mem = retrieved_memories[0]
    category = top_mem.get("category", "")
    mapped = MOOD_CATEGORY_MAP.get(category)
    if mapped:
        return mapped
    emotion = top_mem.get("emotion", "")
    if emotion in ("Joyful", "Heartwarming"):
        return "happy"
    return "calm"


def detect_mood_from_answer(answer: str) -> str:
    """Refine mood based on answer text keywords."""
    if not answer:
        return "calm"
    t = answer.lower()
    if any(w in t for w in ["proud", "achieved", "success", "won"]):
        return "proud"
    if any(w in t for w in ["funny", "joke", "laughed", "hilarious", "humor"]):
        return "funny"
    if any(w in t for w in ["kind", "help", "faith", "generous", "grateful"]):
        return "kind"
    if any(w in t for w in ["advice", "wise", "lesson", "learn", "thought"]):
        return "thoughtful"
    if any(w in t for w in ["happy", "wonderful", "beautiful", "love"]):
        return "happy"
    return "calm"


def create_avatar_action_plan(answer: str, retrieved_memories: list, companion_type: str = "female") -> dict:
    """
    Create an action plan dict for the frontend avatar.

    Returns:
    {
        "mood": "...",
        "expression": "...",
        "gesture": "...",
        "movement": "...",
        "mouth_style": "normal | excited | slow",
        "camera": "close | medium | idle",
        "short_spoken_summary": "...",
        "animation_cues": [...]
    }
    """
    # Detect mood
    mood = detect_mood_from_memories(retrieved_memories)
    if mood == "calm":
        mood = detect_mood_from_answer(answer)

    # Map mood to expression, gesture, movement
    expression_map = {
        "calm": "gentle_smile",
        "happy": "bright_smile",
        "thoughtful": "soft_frown",
        "funny": "grin",
        "kind": "warm_smile",
        "proud": "confident_smile",
        "bored": "gentle_yawn",
    }

    gesture_map = {
        "calm": "hands_relaxed",
        "happy": "hands_open",
        "thoughtful": "hand_chin",
        "funny": "hand_wave",
        "kind": "hand_heart",
        "proud": "hands_chest",
        "bored": "head_tilt",
    }

    movement_map = {
        "calm": "still",
        "happy": "gentle_bounce",
        "thoughtful": "slow_turn",
        "funny": "lean_forward",
        "kind": "lean_in",
        "proud": "stand_tall",
        "bored": "slouch",
    }

    mouth_map = {
        "calm": "normal",
        "happy": "excited",
        "thoughtful": "slow",
        "funny": "excited",
        "kind": "slow",
        "proud": "excited",
        "bored": "slow",
    }

    # Generate short spoken summary (first sentence of answer, truncated)
    short_summary = ""
    if answer:
        short_summary = answer.split(".")[0][:120] + ("." if len(answer.split(".")[0]) < 120 else "...")

    # Animation timing cues
    animation_cues = [
        {"time": 0.0, "action": "expression_set", "value": expression_map.get(mood, "gentle_smile")},
        {"time": 0.3, "action": "mood_activate", "value": mood},
        {"time": 0.5, "action": "speak_start"},
    ]

    # If mood is bored, add special cue
    if mood == "bored":
        animation_cues.append({
            "time": 1.0,
            "action": "speak_text",
            "value": "I'm getting a little dry here. Give me a fresh memory and I'll wake up.",
        })

    return {
        "mood": mood,
        "expression": expression_map.get(mood, "gentle_smile"),
        "gesture": gesture_map.get(mood, "hands_relaxed"),
        "movement": movement_map.get(mood, "still"),
        "mouth_style": mouth_map.get(mood, "normal"),
        "camera": "medium",
        "short_spoken_summary": short_summary,
        "animation_cues": animation_cues,
        "director": "instant_rules",
    }


def _extract_json_object(text: str) -> dict:
    """Parse the first complete JSON object from a model response."""
    if not text:
        return {}
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            continue
    return {}


def _validated_model_fields(payload: dict) -> dict:
    safe = {}
    for key, allowed in ALLOWED_ACTIONS.items():
        value = str(payload.get(key, "")).strip().lower()
        if value in allowed:
            safe[key] = value
    return safe


def create_model_avatar_action_plan(
    answer: str,
    retrieved_memories: list,
    companion_type: str = "female",
    fallback_plan: dict | None = None,
) -> dict:
    """Refine the instant plan with local ModelScope Qwen3-0.6B output."""
    from backend.models.avatar_action_loader import (
        avatar_action_model_ready,
        generate_avatar_action_json,
    )

    base = fallback_plan or create_avatar_action_plan(answer, retrieved_memories, companion_type)
    if not avatar_action_model_ready():
        return {**base, "director": "instant_rules", "director_ready": False}

    memory_signals = [
        {
            "category": str(memory.get("category", ""))[:48],
            "emotion": str(memory.get("emotion", ""))[:32],
        }
        for memory in (retrieved_memories or [])[:3]
        if isinstance(memory, dict)
    ]
    user_payload = {
        "companion": companion_type,
        "answer": str(answer or "")[:600],
        "memory_signals": memory_signals,
        "instant_plan": {key: base.get(key) for key in ALLOWED_ACTIONS},
    }
    started = time.perf_counter()
    raw = generate_avatar_action_json([
        {"role": "system", "content": ACTION_DIRECTOR_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=True)},
    ])
    model_fields = _validated_model_fields(_extract_json_object(raw))
    if len(model_fields) < 3:
        logger.warning("Avatar action model returned an incomplete plan; retaining instant rules.")
        return {**base, "director": "instant_rules", "director_ready": True}

    return {
        **base,
        **model_fields,
        "director": "modelscope_qwen3_0_6b",
        "director_ready": True,
        "director_ms": round((time.perf_counter() - started) * 1000, 1),
    }
