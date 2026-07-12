"""
Memory Twin AI — Companion Profiles

Two safe synthetic adult companion profiles:
- Male Adult Companion
- Female Adult Companion

No real person data. No real voice clones. Non-sexual synthetic assistants.
"""
COMPANION_PROFILES = {
    "male": {
        "label": "Male Adult Companion",
        "voice_profile": "male_adult_warm",
        "tts_pitch": 0.9,
        "tts_rate": 0.92,
        "base_mood": "calm",
        "speech_style": "warm, direct, slightly witty, emotionally grounded",
        "safety": "non-sexual synthetic assistant for hackathon demo",
    },
    "female": {
        "label": "Female Adult Companion",
        "voice_profile": "female_adult_warm",
        "tts_pitch": 1.08,
        "tts_rate": 0.94,
        "base_mood": "kind",
        "speech_style": "gentle, expressive, thoughtful, lightly playful",
        "safety": "non-sexual synthetic assistant for hackathon demo",
    },
}


def get_companion_profile(companion_type: str = "female") -> dict:
    """Return profile dict for the given companion type."""
    profile = COMPANION_PROFILES.get(companion_type)
    if not profile:
        profile = COMPANION_PROFILES["female"]
    return profile


def get_voice_settings(companion_type: str, mood: str = "calm") -> dict:
    """
    Return TTS voice settings adjusted by mood.

    happy: slightly faster, brighter
    thoughtful: slower, softer
    funny: playful pace
    kind: gentle, warm
    bored: slower, lower energy (not rude)
    """
    profile = get_companion_profile(companion_type)
    pitch = profile["tts_pitch"]
    rate = profile["tts_rate"]

    mood_adjustments = {
        "happy": {"rate_offset": 0.06, "pitch_offset": 0.04},
        "thoughtful": {"rate_offset": -0.08, "pitch_offset": -0.03},
        "funny": {"rate_offset": 0.04, "pitch_offset": 0.06},
        "kind": {"rate_offset": -0.02, "pitch_offset": 0.02},
        "bored": {"rate_offset": -0.06, "pitch_offset": -0.04},
        "proud": {"rate_offset": 0.02, "pitch_offset": 0.03},
    }

    adj = mood_adjustments.get(mood, {"rate_offset": 0, "pitch_offset": 0})
    rate = max(0.5, min(2.0, rate + adj["rate_offset"]))
    pitch = max(0.5, min(2.0, pitch + adj["pitch_offset"]))

    return {
        "voice_profile": profile["voice_profile"],
        "pitch": round(pitch, 2),
        "rate": round(rate, 2),
        "companion_type": companion_type,
        "mood": mood,
    }
