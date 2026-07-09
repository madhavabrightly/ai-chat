"""
Memory Twin AI — Verify Selected Models

Verifies downloaded models exist and can be loaded.
Finds models in both preferred and legacy cache paths.

Usage:
    python backend/scripts/verify_selected_models.py
    python backend/scripts/verify_selected_models.py --check-llm
    python backend/scripts/verify_selected_models.py --check-tts
    python backend/scripts/verify_selected_models.py --check-asr
    python backend/scripts/verify_selected_models.py --check-avatar
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.models.model_registry import print_model_registry, get_model_status, get_model_path
from backend.config import MODEL_ROOT, FORCE_CPU


def check_torch():
    import torch
    print(f"\n  Torch:     {torch.__version__}")
    print(f"  CUDA:      {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  Device:    {torch.cuda.get_device_name(0)}")
    else:
        print(f"  Device:    CPU (FORCE_CPU={FORCE_CPU})")


def check_embedding():
    print("\n--- Checking embedding model ---")
    from backend.models.embedding_loader import load_embedder, embed_query
    load_embedder()
    vec = embed_query("What advice would you give me?")
    print(f"  Embedding OK — dimension: {len(vec)}")


def check_llm():
    print("\n--- Checking LLM ---")
    status = get_model_status()
    llm = status.get("llm", {})
    if llm.get("exists_locally"):
        print(f"  LLM found in: {llm['active_path']} [{llm['source']}]")
        print(f"  No redownload needed.")
    else:
        print(f"  LLM not found in any path.")
        return
    from backend.models.llm_loader import load_llm, generate_answer
    load_llm()
    answer = generate_answer(
        "You are a helpful assistant. Answer briefly.",
        [{"role": "user", "content": "Say hello in one word."}],
    )
    print(f"  LLM response: {answer[:100]}")


def check_tts():
    print("\n--- Checking TTS (CosyVoice) ---")
    status = get_model_status()
    tts = status.get("tts", {})
    print(f"  Exists: {tts.get('exists_locally', False)}")
    print(f"  Path:   {tts.get('active_path', 'N/A')}")
    if tts.get("exists_locally"):
        print(f"  TTS files found but full load verification may be partial.")
    else:
        print(f"  TTS files incomplete or missing. Browser TTS fallback will be used.")


def check_asr():
    print("\n--- Checking ASR (SenseVoiceSmall) ---")
    status = get_model_status()
    asr_status = status.get("asr", {})
    print(f"  Exists: {asr_status.get('exists_locally', False)}")
    print(f"  Path:   {asr_status.get('active_path', 'N/A')}")
    if not asr_status.get("exists_locally"):
        print(f"  ASR missing. Browser SpeechRecognition fallback will be used.")
    else:
        print(f"  ASR found locally.")


def check_avatar():
    print("\n--- Checking Avatar Video (MuseTalk) ---")
    status = get_model_status()
    av = status.get("avatar_video", {})
    print(f"  Exists: {av.get('exists_locally', False)}")
    print(f"  Path:   {av.get('active_path', 'N/A')}")
    from backend.config import ENABLE_MUSETALK
    print(f"  ENABLE_MUSETALK: {ENABLE_MUSETALK}")
    if not av.get("exists_locally"):
        print(f"  MuseTalk missing. CSS live avatar fallback will be used.")
    else:
        print(f"  MuseTalk found locally.")


def main():
    parser = argparse.ArgumentParser(description="Verify downloaded Memory Twin AI models")
    parser.add_argument("--check-llm", action="store_true", help="Verify LLM by generating a response")
    parser.add_argument("--check-tts", action="store_true", help="Verify TTS model")
    parser.add_argument("--check-asr", action="store_true", help="Verify ASR model")
    parser.add_argument("--check-avatar", action="store_true", help="Verify MuseTalk model")
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print(f"Memory Twin AI — Model Verification")
    print(f"{'='*55}")
    print(f"Model root: {MODEL_ROOT}")

    check_torch()
    print_model_registry()

    if args.check_llm:
        check_llm()
    elif args.check_tts:
        check_tts()
    elif args.check_asr:
        check_asr()
    elif args.check_avatar:
        check_avatar()
    else:
        check_embedding()
        print("\nTip: Use --check-llm, --check-tts, --check-asr, or --check-avatar for deeper verification.")

    print(f"\n{'='*55}")
    print("Verification complete.")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
