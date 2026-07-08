"""
Memory Twin AI — Configuration
AMD Developer Hackathon 2026 | Track 3: Unicorn / Open Innovation

Model Storage Rules:
  - Default: /workspace/memory_twin_models
  - Fallback: ./runtime_cache/models
  - NEVER store weights inside the git repo.
  - .gitignore excludes model weight extensions and cache dirs.

ChromaDB Storage Rules:
  - Default: /workspace/memory_twin_chroma
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

# Model cache — try env var, then default workspace path, then fallback
MODEL_CACHE_DIR = os.getenv(
    "MODEL_CACHE_DIR",
    "/workspace/memory_twin_models",
)
if not os.path.exists(MODEL_CACHE_DIR):
    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

# ChromaDB persistence path
CHROMA_DB_DIR = os.getenv(
    "CHROMA_DB_DIR",
    "/workspace/memory_twin_chroma",
)
if not os.path.exists(CHROMA_DB_DIR):
    os.makedirs(CHROMA_DB_DIR, exist_ok=True)

# Memories data file
MEMORIES_PATH = os.path.join(BASE_DIR, "data", "memories.json")

# Datasets directory (downloaded from ModelScope)
DATASETS_DIR = os.getenv(
    "DATASETS_DIR",
    os.path.join(PROJECT_ROOT, "datasets"),
)
if not os.path.exists(DATASETS_DIR):
    os.makedirs(DATASETS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Model config
# ---------------------------------------------------------------------------
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B")

# Force CPU mode (set FORCE_CPU=true in .env)
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
TOP_K = 3

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are Memory Twin AI, a consent-based digital memory simulation. "
    "You answer only using the provided memory context. "
    "Speak warmly, naturally, and briefly. "
    "Do not claim to be the real person. "
    "If the answer is not in memory, say the memory is unclear and gently connect to a related known memory."
)
