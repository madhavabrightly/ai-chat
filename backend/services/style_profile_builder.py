"""
Memory Twin AI — Style Profile Builder

Builds and stores companion style profiles from imported text.
"""
import json
import os
import uuid
from backend.config import RUNTIME_ROOT

STYLE_DIR = os.path.join(RUNTIME_ROOT, "style_profiles")
os.makedirs(STYLE_DIR, exist_ok=True)
IMPORTS_DIR = os.path.join(RUNTIME_ROOT, "imports")
os.makedirs(IMPORTS_DIR, exist_ok=True)


def save_style_profile(profile: dict) -> str:
    """Save a style profile to runtime storage. Returns profile ID."""
    profile_id = profile.get("style_profile_id", "style_" + uuid.uuid4().hex[:8])
    path = os.path.join(STYLE_DIR, f"{profile_id}.json")
    with open(path, "w") as f:
        json.dump(profile, f, indent=2)
    return profile_id


def load_style_profile(profile_id: str) -> dict:
    """Load a style profile from runtime storage."""
    path = os.path.join(STYLE_DIR, f"{profile_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def list_style_profiles() -> list[dict]:
    """List all saved style profiles."""
    profiles = []
    if not os.path.isdir(STYLE_DIR):
        return profiles
    for fn in os.listdir(STYLE_DIR):
        if fn.endswith(".json"):
            with open(os.path.join(STYLE_DIR, fn)) as f:
                profiles.append(json.load(f))
    return profiles


def get_active_style_profile() -> dict:
    """Return the active style profile, if any."""
    active_path = os.path.join(STYLE_DIR, "_active.json")
    if os.path.exists(active_path):
        with open(active_path) as f:
            data = json.load(f)
        profile = load_style_profile(data.get("profile_id", ""))
        if profile:
            return profile
    return None


def set_active_style_profile(profile_id: str):
    """Set a style profile as active."""
    path = os.path.join(STYLE_DIR, "_active.json")
    with open(path, "w") as f:
        json.dump({"profile_id": profile_id}, f)
