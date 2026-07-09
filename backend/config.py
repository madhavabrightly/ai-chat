"""
Memory Twin AI — Configuration
AMD Developer Hackathon 2026 | Track 3: Unicorn / Open Innovation

Model Storage Rules:
  - Default: /workspace/memory_twin_models
  - Fallback: ./runtime_cache/models
  - NEVER store weights inside the git repo.
  - .gitignore excludes model weight extensions and cache dirs.

ChromaDB Storage Rules:
  - Default: /workspace/memory_twin_runtime/chroma_db
  - Fallback: ./runtime_cache/chroma
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Model root — all selected models stored here in subdirs
MODEL_ROOT = os.getenv("MODEL_ROOT", "/workspace/memory_twin_models")
os.makedirs(MODEL_ROOT, exist_ok=True)

# Runtime root — generated audio, video clips, logs, ChromaDB
RUNTIME_ROOT = os.getenv("RUNTIME_ROOT", "/workspace/memory_twin_runtime")
os.makedirs(RUNTIME_ROOT, exist_ok=True)

# ChromaDB persistence path
CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", os.path.join(RUNTIME_ROOT, "chroma_db"))
os.makedirs(CHROMA_DB_DIR, exist_ok=True)

# Generated media paths
GENERATED_AUDIO_DIR = os.getenv("GENERATED_AUDIO_DIR", os.path.join(RUNTIME_ROOT, "generated_audio"))
os.makedirs(GENERATED_AUDIO_DIR, exist_ok=True)

GENERATED_AVATAR_DIR = os.getenv("GENERATED_AVATAR_DIR", os.path.join(RUNTIME_ROOT, "generated_avatar_clips"))
os.makedirs(GENERATED_AVATAR_DIR, exist_ok=True)

# Memories data file
MEMORIES_PATH = os.path.join(BASE_DIR, "data", "memories.json")

# Datasets directory
DATASETS_DIR = os.getenv("DATASETS_DIR", os.path.join(PROJECT_ROOT, "datasets"))
os.makedirs(DATASETS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Legacy model cache path (backwards compat)
# ---------------------------------------------------------------------------
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", MODEL_ROOT)
os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Model IDs (from ModelScope)
# ---------------------------------------------------------------------------
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "Qwen/Qwen2.5-7B-Instruct")
EMBEDDING_MODEL_ID = os.getenv("EMBEDDING_MODEL_ID", "Qwen/Qwen3-Embedding-0.6B")
RERANKER_MODEL_ID = os.getenv("RERANKER_MODEL_ID", "Qwen/Qwen3-Reranker-0.6B")
TTS_MODEL_ID = os.getenv("TTS_MODEL_ID", "iic/CosyVoice-300M")
TTS2_MODEL_ID = os.getenv("TTS2_MODEL_ID", "iic/CosyVoice2-0.5B")
ASR_MODEL_ID = os.getenv("ASR_MODEL_ID", "iic/SenseVoiceSmall")
EMOTION_MODEL_ID = os.getenv("EMOTION_MODEL_ID", "iic/emotion2vec_plus_large")
AVATAR_VIDEO_MODEL_ID = os.getenv("AVATAR_VIDEO_MODEL_ID", "AI-ModelScope/MuseTalk")

# Backwards compat names
LLM_MODEL_NAME = LLM_MODEL_ID
EMBEDDING_MODEL_NAME = EMBEDDING_MODEL_ID

# ---------------------------------------------------------------------------
# Toggle flags
# ---------------------------------------------------------------------------
ENABLE_MUSETALK = os.getenv("ENABLE_MUSETALK", "false").lower() == "true"
ENABLE_MODEL_TTS = os.getenv("ENABLE_MODEL_TTS", "true").lower() == "true"
ENABLE_MODEL_ASR = os.getenv("ENABLE_MODEL_ASR", "true").lower() == "true"
ENABLE_RERANKER = os.getenv("ENABLE_RERANKER", "true").lower() == "true"
ENABLE_EMOTION = os.getenv("ENABLE_EMOTION", "true").lower() == "true"
ENABLE_TTS2 = os.getenv("ENABLE_TTS2", "false").lower() == "true"
# Qwen Omni — future premium mode. Not default.
ENABLE_QWEN_OMNI = os.getenv("ENABLE_QWEN_OMNI", "false").lower() == "true"

# Force CPU mode
FORCE_CPU = os.getenv("FORCE_CPU", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Embedding config
# ---------------------------------------------------------------------------
EMBEDDING_QUERY_INSTRUCTION = (
    "Given a user's question, retrieve the most relevant personal memories that can answer it."
)
EMBEDDING_DIMENSION = 1024  # Qwen3-Embedding-0.6B outputs 1024-dim vectors

# ---------------------------------------------------------------------------
# RAG config
# ---------------------------------------------------------------------------
TOP_K = int(os.getenv("TOP_K_MEMORIES", "3"))
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "384"))

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are Memory Twin AI, a consent-based digital memory simulation.\n"
    "Respond only in English. Do not use Chinese, Tamil, Hindi, or mixed-language text.\n"
    "Use the provided memory context when relevant.\n"
    "If the answer is not in memory, say clearly that the memory is not saved yet.\n"
    "You may answer general identity/app questions independently, "
    "but label them as app behavior, not personal memory.\n"
    "Speak warmly, briefly, and naturally. Do not claim to be a real person.\n"
    "Keep the chat lively, human, and useful."
)
