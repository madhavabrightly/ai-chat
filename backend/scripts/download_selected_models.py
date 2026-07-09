"""
Download selected Memory Twin AI models only.

Downloads only the 5 selected models from ModelScope into MODEL_ROOT.
Skips already-downloaded models. Checks disk space first.
Saves a models_manifest.json on completion.

Usage:
    python backend/scripts/download_selected_models.py
"""
import json
import os
import shutil
import sys

# Ensure backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.models.model_registry import MODEL_SPECS, RUNTIME_DIRS
from backend.config import MODEL_ROOT, RUNTIME_ROOT

try:
    from modelscope import snapshot_download
except ImportError:
    print("ERROR: modelscope not installed. Install with: pip install modelscope")
    sys.exit(1)

# Manually define download order — embedding first (fastest), then TTS, ASR, LLM, MuseTalk last
DOWNLOAD_ORDER = ["embedding", "tts", "asr", "llm", "avatar_video"]


def check_disk_space_gb(path: str) -> float:
    """Return available disk space in GB."""
    usage = shutil.disk_usage(path)
    return usage.free / (1024 ** 3)


def download_selected_models():
    print("\n" + "=" * 56)
    print("Downloading selected Memory Twin AI models only.")
    print("Do not commit this model folder to GitHub.")
    print("=" * 56)

    # Create directories
    os.makedirs(MODEL_ROOT, exist_ok=True)
    for dir_path in RUNTIME_DIRS.values():
        os.makedirs(dir_path, exist_ok=True)

    # Check disk
    available_gb = check_disk_space_gb(MODEL_ROOT)
    print(f"\nAvailable disk space: {available_gb:.1f} GB")

    if available_gb < 35:
        print("WARNING: Low disk space. Skipping avatar_video (MuseTalk).")
        download_list = [k for k in DOWNLOAD_ORDER if k != "avatar_video"]
    else:
        download_list = DOWNLOAD_ORDER

    manifest = {}
    success_count = 0
    skip_count = 0

    for key in download_list:
        spec = MODEL_SPECS[key]
        target_dir = spec["local_dir"]
        model_id = spec["id"]

        print(f"\n[{success_count + 1}/{len(download_list)}] {model_id}")
        print(f"  Purpose: {spec['purpose']}")
        print(f"  Target:  {target_dir}")

        # Check if already downloaded
        if os.path.isdir(target_dir):
            # Check for weight files
            has_weights = False
            for root, dirs, files in os.walk(target_dir):
                for f in files:
                    if any(f.endswith(ext) for ext in [".safetensors", ".bin", ".pt", ".pth"]):
                        has_weights = True
                        break
                if has_weights:
                    break
            if has_weights:
                print(f"  ✓ Already downloaded — skipping.")
                manifest[key] = {
                    "model_id": model_id,
                    "local_path": target_dir,
                    "status": "exists",
                }
                skip_count += 1
                continue

        # Download
        try:
            print(f"  Downloading...")
            local_path = snapshot_download(
                model_id=model_id,
                cache_dir=target_dir,
            )
            print(f"  ✓ Done: {local_path}")
            manifest[key] = {
                "model_id": model_id,
                "local_path": str(local_path),
                "status": "downloaded",
            }
            success_count += 1
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            manifest[key] = {
                "model_id": model_id,
                "local_path": str(target_dir),
                "status": f"error: {str(e)[:80]}",
            }

    # Save manifest
    manifest_path = os.path.join(MODEL_ROOT, "models_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest saved: {manifest_path}")

    # Summary
    print("\n" + "=" * 56)
    print(f"Download complete.")
    print(f"  Downloaded: {success_count}")
    print(f"  Skipped (exists): {skip_count}")
    print(f"  Total handled: {len(download_list)}")
    print(f"  Model root: {MODEL_ROOT}")
    print("=" * 56)


if __name__ == "__main__":
    download_selected_models()
