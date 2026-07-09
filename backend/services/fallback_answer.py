"""
Memory Twin AI — Safe Fallback Answer System

Produces graceful English answers when LLM fails or memory is missing.
Never crashes. Always returns a valid response object.
"""
import logging

logger = logging.getLogger(__name__)

IDENTITY_ANSWERS = {
    "who are you": "I am Memory Twin AI, a consent-based digital memory simulation. I hold fictional memories and I am here to chat with you about them.",
    "what are you": "I am Memory Twin AI, a digital memory companion. I can remember, retrieve, and talk about memories.",
    "what can you do": "I can remember memories, retrieve stories from my memory vault, answer questions about them, and chat with you naturally. Try asking me about my childhood, advice, or a funny story.",
    "how does this work": "I use RAG (retrieval-augmented generation) to find relevant memories from my vault, then generate a warm natural response using a language model running on AMD compute.",
    "where are you": "I do not have a physical location. I am running as your Memory Twin AI companion inside this app.",
    "are you real": "I am a digital memory simulation, not a real person. I hold fictional memories and respond based on them.",
    "hi": "Hi! I am here. What memory would you like to talk about today?",
    "hello": "Hello! I am your Memory Twin companion. Ask me about a memory.",
    "hey": "Hey there! Ready to explore some memories?",
}

REPETITION_RESPONSES = [
    "I feel like we're circling the same memory. Want to add something new?",
    "We've talked about this before. Tell me something fresh and I'll remember it.",
    "This reminds me of earlier conversations. What else is on your mind?",
]


def build_fallback_answer(question: str = "", companion_type: str = "female",
                          retrieved_memories: list = None, error: str = None) -> dict:
    """
    Build a safe fallback answer when LLM fails or no memory is found.
    Always returns valid response dict.
    """
    question_lower = question.strip().lower() if question else ""

    # Check identity questions
    for key, answer in IDENTITY_ANSWERS.items():
        if key in question_lower:
            return {
                "answer": answer,
                "retrieved_memories": retrieved_memories or [],
                "fallback_used": True,
                "error": False,
            }

    # Personal facts not in memory
    personal_facts = ["date of birth", "dob", "birthday", "birth date",
                      "phone number", "address", "email", "password",
                      "social security", "credit card", "bank account"]
    if any(fact in question_lower for fact in personal_facts):
        return {
            "answer": "I don't have that saved in memory yet. You can tell me and I will remember it.",
            "retrieved_memories": retrieved_memories or [],
            "fallback_used": True,
            "error": False,
        }

    # Location/presence
    location_keys = ["where are you", "where do you live", "your location", "are you here"]
    if any(k in question_lower for k in location_keys):
        return {
            "answer": "I don't have a real physical location. I am running as your Memory Twin AI companion inside this app.",
            "retrieved_memories": retrieved_memories or [],
            "fallback_used": True,
            "error": False,
        }

    # No memory found
    if not retrieved_memories or len(retrieved_memories) == 0:
        return {
            "answer": "I don't have that memory saved yet. You can tell me about it and I will remember it for next time.",
            "retrieved_memories": [],
            "fallback_used": True,
            "error": False,
        }

    # LLM error (memories exist but LLM failed)
    if error:
        return {
            "answer": "I found some memories, but I had trouble putting them into words. Please try asking again.",
            "retrieved_memories": retrieved_memories or [],
            "fallback_used": True,
            "error": True,
            "error_type": error,
        }

    # Generic fallback
    return {
        "answer": "I'm not sure about that yet. Tell me more and I will remember.",
        "retrieved_memories": retrieved_memories or [],
        "fallback_used": True,
        "error": False,
    }
