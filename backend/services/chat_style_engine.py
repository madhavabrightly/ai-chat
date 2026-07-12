"""
Memory Twin AI — Chat Style Engine

Generates dynamic response instructions based on companion type, mood, and context.
Keeps the conversation lively, human, and emotionally aware.

Upgraded to support:
  - Emotion-aware response style injection
  - Citation guidance ([Memory N] references)
  - Persona anchoring to prevent character drift
  - Conversation-turn-aware suggestions
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

CITATION_GUIDE = (
    "When you use information from the provided memories, cite the source as "
    "[Memory N] where N matches the bracketed label in the context. This helps "
    "the user trace where each part of your answer came from."
)

PERSONA_ANCHOR = (
    "Stay in character as your companion persona throughout the response. "
    "Do not break character or mention that you are an AI language model."
)


def create_lively_response_instruction(
    companion_type: str = "female",
    mood: str = "calm",
    user_message: str = "",
    memory_context: str = "",
    conversation_turns: int = 0,
    emotion: str = "",
    response_style: str = "",
) -> str:
    """
    Build a dynamic instruction string for the LLM.

    Combines companion speech style, mood adjustment, emotion-aware tone,
    citation guidance, persona anchor, and repetition guard.
    """
    profile = get_companion_profile(companion_type)
    mood_instruction = MOOD_INSTRUCTIONS.get(mood, MOOD_INSTRUCTIONS["calm"])

    parts = [
        f"You are a {profile['speech_style']} companion.",
        mood_instruction,
        "Speak naturally like a warm human companion. Avoid robotic answers. Avoid long boring lectures.",
        "Use short, useful, emotionally aware responses. Use mild humor only when suitable.",
    ]

    # Emotion-aware tone injection
    if emotion and response_style:
        parts.append(
            f"The user's current emotional state appears to be: {emotion}. "
            f"Adapt your tone to be {response_style}."
        )

    # Citation guidance (only when memory context is present)
    if memory_context:
        parts.append(CITATION_GUIDE)

    # Persona anchor
    parts.append(PERSONA_ANCHOR)

    if conversation_turns > 10:
        parts.append(
            "You've been chatting for a while. Try asking the user something about themselves "
            "or suggest exploring the Memory Atlas."
        )

    parts.append(REPETITION_GUARD)

    return " ".join(parts)
