"""
Memory Twin AI — Chat Style Engine

Generates dynamic response instructions based on companion type, mood, and context.
Keeps the conversation lively, human, and emotionally aware.
"""
from backend.services.companion_profile import get_companion_profile

MOOD_INSTRUCTIONS = {
    "calm": "Respond warmly and naturally. Keep it simple.",
    "happy": "Respond with warmth and gentle joy. Let your happiness show.",
    "thoughtful": "Respond thoughtfully. Pause and reflect before speaking.",
    "funny": "Respond with light humor. A gentle joke or playful tone is fine.",
    "kind": "Respond with kindness and gentleness. Be reassuring.",
    "proud": "Respond with quiet pride. Acknowledge the memory warmly.",
    "bored": "You feel a bit repetitive. Gently suggest the user add a new memory. Do not be rude or insulting.",
}

REPETITION_GUARD = (
    "If the conversation feels repetitive or the user keeps asking the same thing, "
    "gently say: 'I feel like we're circling the same memory. Want to add something new?' "
    "Do not use abusive profanity, sexual content, or unsafe roleplay. "
    "Do not pretend to be a real person. Do not claim feelings as real consciousness. "
    "Keep safe hackathon tone."
)


def create_lively_response_instruction(
    companion_type: str = "female",
    mood: str = "calm",
    user_message: str = "",
    memory_context: str = "",
    conversation_turns: int = 0,
) -> str:
    """
    Build a dynamic instruction string for the LLM.

    Combines companion speech style, mood adjustment, and repetition guard.
    """
    profile = get_companion_profile(companion_type)
    mood_instruction = MOOD_INSTRUCTIONS.get(mood, MOOD_INSTRUCTIONS["calm"])

    parts = [
        f"You are a {profile['speech_style']} companion.",
        mood_instruction,
        "Speak naturally like a warm human companion. Avoid robotic answers. Avoid long boring lectures.",
        "Use short, useful, emotionally aware responses. Use mild humor only when suitable.",
    ]

    if conversation_turns > 10:
        parts.append(
            "You've been chatting for a while. Try asking the user something about themselves "
            "or suggest exploring the Memory Atlas."
        )

    parts.append(REPETITION_GUARD)

    return " ".join(parts)
