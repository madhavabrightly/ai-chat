"""Download the optional Qwen3-0.6B GLB action director from ModelScope."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.models.model_registry import MODEL_SPECS, model_is_loadable


def main():
    try:
        from modelscope import snapshot_download
    except ImportError:
        raise SystemExit("ModelScope is not installed. Install backend requirements first.")

    spec = MODEL_SPECS["avatar_action"]
    target = spec["preferred_dir"]
    if model_is_loadable("avatar_action"):
        print(f"Avatar action model already ready: {target}")
        return

    os.makedirs(target, exist_ok=True)
    print(f"Downloading {spec['id']} to {target}")
    snapshot_download(model_id=spec["id"], local_dir=target)
    if not model_is_loadable("avatar_action"):
        raise SystemExit("Download finished but required model files were not found.")
    print(f"Avatar action model ready: {target}")


if __name__ == "__main__":
    main()
