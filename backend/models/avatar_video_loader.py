"""
Memory Twin AI — Avatar Video Loader (MuseTalk)

Optional enhanced anime/lip-sync avatar clips.
Only loaded if ENABLE_MUSETALK=true.
If unavailable, returns fallback_live_animation signal.
"""
import logging
import os
from backend.config import ENABLE_MUSETALK
from backend.models.model_registry import get_model_path

logger = logging.getLogger(__name__)

# Global singleton
avatar_video_model = None


def load_avatar_video():
    """Load MuseTalk model if ENABLE_MUSETALK=true."""
    global avatar_video_model
    if not ENABLE_MUSETALK:
        logger.info("MuseTalk disabled (ENABLE_MUSETALK=false). Using lightweight live animation.")
        return None

    local_path = get_model_path("avatar_video")

    if not os.path.isdir(local_path):
        logger.warning(f"MuseTalk not found locally. Avatar will use lightweight animation.")
        return None

    try:
        # MuseTalk imports and loading would go here
        # For now, return None to use lightweight live avatar
        logger.info("MuseTalk loading stub — use lightweight CSS avatar for now.")
        avatar_video_model = None
        return None
    except Exception as e:
        logger.warning(f"MuseTalk load failed: {e}. Using lightweight animation.")
        avatar_video_model = None
        return None


def get_avatar_video():
    """Return loaded avatar model or None."""
    return avatar_video_model


def generate_avatar_clip(audio_path: str, companion_type: str = "female", mood: str = "calm") -> dict:
    """
    Generate enhanced lip-sync avatar clip.

    If MuseTalk is unavailable or slow, returns fallback_live_animation.
    """
    if avatar_video_model is None:
        return {"status": "fallback_live_animation", "reason": "MuseTalk not loaded or disabled"}
    try:
        # MuseTalk inference stub
        return {"status": "fallback_live_animation", "reason": "MuseTalk inference not yet wired"}
    except Exception as e:
        return {"status": "fallback_live_animation", "reason": str(e)}
