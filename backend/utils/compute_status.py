import logging
import torch
from backend.config import (
    LLM_MODEL_NAME,
    EMBEDDING_MODEL_NAME,
    TTS_MODEL_ID,
    ASR_MODEL_ID,
    MODEL_ROOT,
    RUNTIME_ROOT,
    CHROMA_DB_DIR,
    GENERATED_AUDIO_DIR,
    GENERATED_AVATAR_DIR,
)

logger = logging.getLogger(__name__)


def get_compute_status() -> dict:
    """
    Return a detailed dict describing the current compute environment.
    Prints a prominent AMD status block to stdout for demo recording.
    """
    torch_version = torch.__version__
    cuda_available = torch.cuda.is_available()
    device_name = "CPU"

    if cuda_available:
        device_name = torch.cuda.get_device_name(0)
        # ROCm exposes AMD GPUs through torch.cuda, so this is the AMD path
        cuda_version = torch.version.cuda or "ROCm (AMD)"
    else:
        # Check for AMD ROCm HIP directly
        hip_available = hasattr(torch, "hip") and torch.hip.is_available()
        if hip_available:
            device_name = f"AMD GPU (ROCm): {torch.hip.get_device_name(0)}"
            cuda_version = "ROCm"
        else:
            cuda_version = "N/A"

    status = {
        "torch_version": torch_version,
        "cuda_or_rocm_version": cuda_version,
        "cuda_available": cuda_available,
        "device": device_name,
        "llm_model": LLM_MODEL_NAME,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "tts_model": TTS_MODEL_ID,
        "asr_model": ASR_MODEL_ID,
        "model_root": MODEL_ROOT,
        "runtime_root": RUNTIME_ROOT,
        "chromadb_path": CHROMA_DB_DIR,
        "generated_audio_dir": GENERATED_AUDIO_DIR,
        "generated_avatar_dir": GENERATED_AVATAR_DIR,
        "task": "Memory retrieval + RAG response generation",
        "note": "For AMD ROCm, PyTorch exposes AMD GPU through torch.cuda APIs. "
                "On an AMD GPU with ROCm, torch.cuda.is_available() returns True "
                "and the device name shows the AMD GPU model.",
    }

    # Print colored terminal block for demo
    print("\n" + "=" * 46)
    print("========== AMD COMPUTE STATUS ==========")
    print(f"Torch Version: {torch_version}")
    print(f"GPU Available: {cuda_available}")
    print(f"Device: {device_name}")
    print(f"LLM Model: {LLM_MODEL_NAME}")
    print(f"Embedding Model: {EMBEDDING_MODEL_NAME}")
    print(f"Model Cache: {MODEL_ROOT}")
    print(f"ChromaDB Path: {CHROMA_DB_DIR}")
    print(f"TTS Model: {TTS_MODEL_ID}")
    print(f"ASR Model: {ASR_MODEL_ID}")
    print(f"Runtime: {RUNTIME_ROOT}")
    print(f"Task: Memory retrieval + RAG response generation")
    print("=" * 46 + "\n")

    return status
