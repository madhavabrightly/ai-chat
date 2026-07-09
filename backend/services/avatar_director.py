"""
Memory Twin AI — Avatar Director

Converts chat answer + retrieved memories into avatar action instructions.
The frontend uses these instructions to drive the lightweight live animation.
"""
import logging

logger = logging.getLogger(__name__)

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
    }
