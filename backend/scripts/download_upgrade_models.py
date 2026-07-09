"""
Download upgrade models for Realtime Emotional Memory Call Engine.

Downloads:
- Qwen3-Reranker-0.6B
- iic/SenseVoiceSmall (if not already present)
- iic/CosyVoice2-0.5B (if disk space allows)
- iic/emotion2vec_plus_large (if disk space allows)

Does NOT redownload existing Qwen LLM or embedding models.
Does NOT download Qwen Omni or video diffusion.
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.models.model_registry import MODEL_ROOT, MODEL_SPECS

try:
    from modelscope import snapshot_download
except ImportError:
    print("ERROR: modelscope not installed.")
    sys.exit(1)

UPGRADE_KEYS = ["reranker", "asr", "tts2", "emotion"]


def check_disk_gb(path):
    usage = shutil.disk_usage(path)
    return usage.free / (1024 ** 3)


def download_upgrade_models():
    print("\n" + "=" * 56)
    print("Downloading upgrade models for Realtime Engine")
    print("=" * 56)

    available_gb = check_disk_gb(MODEL_ROOT)
    print(f"Available disk: {available_gb:.1f} GB")

    # If disk < 20 GB, skip tts2 and emotion
    skip = []
    if available_gb < 20:
        skip = ["tts2", "emotion"]
        print("Low disk. Skipping CosyVoice2 and emotion2vec.")

    for key in UPGRADE_KEYS:
        if key in skip:
            print(f"\n  Skipping {key} (disk space)")
            continue
        spec = MODEL_SPECS.get(key)
        if not spec:
            continue
        model_id = spec["id"]
        target = spec["preferred_dir"]
        print(f"\n  [{UPGRADE_KEYS.index(key)+1}/{len(UPGRADE_KEYS)}] {model_id}")
        print(f"  Target: {target}")

        if os.path.isdir(target) and any(
            f.endswith((".safetensors", ".bin", ".pt"))
            for _, _, files in os.walk(target)
            for f in files
        ):
            print("  Already exists — skipping.")
            continue

        try:
            snapshot_download(model_id, cache_dir=str(target))
            print("  Done.")
        except Exception as e:
            print(f"  Failed: {e}")

    print("\n" + "=" * 56)
    print("Upgrade models download complete.")
    print("=" * 56)


if __name__ == "__main__":
    download_upgrade_models()
