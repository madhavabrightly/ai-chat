"""
Memory Twin AI — Model Registry
Single source of truth for all selected model paths and metadata.
Supports legacy cache paths (from ModelScope) and new preferred paths.
"""
import os
from backend.config import MODEL_ROOT, RUNTIME_ROOT

# Legacy paths are old ModelScope cache dirs (already on disk)
LEGACY_PATHS = {
    "llm": os.path.join(MODEL_ROOT, "Qwen_Qwen2.5-7B-Instruct"),
    "embedding": os.path.join(MODEL_ROOT, "Qwen_Qwen3-Embedding-0.6B"),
}

MODEL_SPECS = {
    "llm": {
        "id": "Qwen/Qwen2.5-7B-Instruct",
        "preferred_dir": os.path.join(MODEL_ROOT, "qwen_llm"),
        "legacy_dirs": [LEGACY_PATHS["llm"]],
        "purpose": "Memory-based answer generation",
        "size_gb": 4.0,
    },
    "embedding": {
        "id": "Qwen/Qwen3-Embedding-0.6B",
        "preferred_dir": os.path.join(MODEL_ROOT, "qwen_embedding"),
        "legacy_dirs": [LEGACY_PATHS["embedding"]],
        "purpose": "Memory retrieval embeddings",
        "size_gb": 0.6,
    },
    "tts": {
        "id": "iic/CosyVoice-300M",
        "preferred_dir": os.path.join(MODEL_ROOT, "cosyvoice_tts"),
        "legacy_dirs": [os.path.join(MODEL_ROOT, "CosyVoice-300M")],
        "purpose": "Synthetic companion speech",
        "size_gb": 1.5,
    },
    "asr": {
        "id": "iic/SenseVoiceSmall",
        "preferred_dir": os.path.join(MODEL_ROOT, "sensevoice_asr"),
        "legacy_dirs": [],
        "purpose": "Speech input transcription",
        "size_gb": 0.5,
    },
    "reranker": {
        "id": "Qwen/Qwen3-Reranker-0.6B",
        "preferred_dir": os.path.join(MODEL_ROOT, "qwen_reranker"),
        "legacy_dirs": [],
        "purpose": "Re-rank retrieved memories for exactness",
        "size_gb": 0.6,
    },
    "emotion": {
        "id": "iic/emotion2vec_plus_large",
        "preferred_dir": os.path.join(MODEL_ROOT, "emotion2vec"),
        "legacy_dirs": [],
        "purpose": "Emotion detection from audio/text",
        "size_gb": 0.5,
    },
    "tts2": {
        "id": "iic/CosyVoice2-0.5B",
        "preferred_dir": os.path.join(MODEL_ROOT, "cosyvoice2_tts"),
        "legacy_dirs": [],
        "purpose": "Enhanced TTS with emotion-aware speech",
        "size_gb": 1.5,
    },
    "avatar_video": {
        "id": "AI-ModelScope/MuseTalk",
        "preferred_dir": os.path.join(MODEL_ROOT, "musetalk_avatar"),
        "legacy_dirs": [],
        "purpose": "Optional lip-sync avatar video",
        "size_gb": 3.0,
    },
}

RUNTIME_DIRS = {
    "chroma_db": os.path.join(RUNTIME_ROOT, "chroma_db"),
    "generated_audio": os.path.join(RUNTIME_ROOT, "generated_audio"),
    "generated_avatar": os.path.join(RUNTIME_ROOT, "generated_avatar_clips"),
    "logs": os.path.join(RUNTIME_ROOT, "logs"),
}


def _has_weight_files(directory: str) -> bool:
    """Check if a directory contains model weight files."""
    if not os.path.isdir(directory):
        return False
    for root, dirs, files in os.walk(directory):
        for f in files:
            if any(f.endswith(ext) for ext in [".safetensors", ".bin", ".pt", ".pth"]):
                return True
    return False


def _has_config_file(directory: str) -> bool:
    """Check if a directory contains a config.json."""
    if not os.path.isdir(directory):
        return False
    for root, dirs, files in os.walk(directory):
        if "config.json" in files:
            return True
    return False


def _find_active_path(spec: dict) -> dict:
    """
    Find the active path for a model spec.
    Checks preferred_dir first, then legacy_dirs, then falls back.
    Returns dict with path, source, and exists status.
    """
    # Check preferred dir
    pref = spec["preferred_dir"]
    if _has_weight_files(pref) or _has_config_file(pref):
        return {"path": pref, "source": "preferred"}

    # Check legacy dirs
    for legacy in spec.get("legacy_dirs", []):
        if _has_weight_files(legacy) or _has_config_file(legacy):
            # Optionally create symlink from preferred -> legacy
            try:
                if not os.path.exists(pref) and os.path.isdir(legacy):
                    os.symlink(legacy, pref)
            except (OSError, PermissionError):
                pass  # symlink failed, still use legacy path
            return {"path": legacy, "source": "legacy"}

    # Fallback: just return preferred dir
    return {"path": pref, "source": "not_found"}


def get_model_path(model_key: str) -> str:
    """Return the active local path for a model key."""
    spec = MODEL_SPECS.get(model_key)
    if not spec:
        raise KeyError(f"Unknown model key: {model_key}. Valid: {list(MODEL_SPECS.keys())}")
    info = _find_active_path(spec)
    return info["path"]


def model_exists_locally(model_key: str) -> bool:
    """Check if a model's active path has weight files."""
    spec = MODEL_SPECS.get(model_key)
    if not spec:
        return False
    info = _find_active_path(spec)
    return _has_weight_files(info["path"])


def model_is_loadable(model_key: str) -> bool:
    """Check if a model has config.json and weight files."""
    spec = MODEL_SPECS.get(model_key)
    if not spec:
        return False
    info = _find_active_path(spec)
    has_config = _has_config_file(info["path"])
    has_weights = _has_weight_files(info["path"])
    return has_config and has_weights


def get_model_status() -> dict:
    """Return dict of all models with detailed status."""
    status = {}
    for key, spec in MODEL_SPECS.items():
        info = _find_active_path(spec)
        has_weights = _has_weight_files(info["path"])
        fallback = None

        if key == "asr" and not has_weights:
            fallback = "browser_speech_recognition"
        elif key == "avatar_video" and not has_weights:
            fallback = "css_live_avatar"
        elif key == "tts" and not has_weights:
            fallback = "browser_tts"

        status[key] = {
            "id": spec["id"],
            "exists_locally": has_weights,
            "active_path": info["path"],
            "preferred_path": spec["preferred_dir"],
            "source": info["source"],
            "loadable": model_is_loadable(key),
            "purpose": spec["purpose"],
            "fallback": fallback,
        }
    return status


def print_model_registry():
    """Pretty-print the model registry."""
    print("\n" + "=" * 55)
    print("Memory Twin AI — Model Registry")
    print("=" * 55)
    for key, spec in MODEL_SPECS.items():
        info = _find_active_path(spec)
        has_weights = _has_weight_files(info["path"])
        status_char = "✓" if has_weights else "✗"
        src = info["source"]
        print(f"  [{status_char}] {key:15s} → {spec['id']}")
        print(f"        Path: {info['path']}  [{src}]")
        print(f"        Role: {spec['purpose']}")
        if not has_weights:
            fallback_map = {
                "llm": "CRITICAL — app will not work",
                "embedding": "CRITICAL — RAG will not work",
                "tts": "browser_tts fallback",
                "asr": "browser_speech_recognition fallback",
                "avatar_video": "css_live_avatar fallback",
            }
            print(f"        Fallback: {fallback_map.get(key, 'unavailable')}")
    print("=" * 55 + "\n")
