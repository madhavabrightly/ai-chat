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
AVATAR_ACTION_MODEL_ID = os.getenv("AVATAR_ACTION_MODEL_ID", "Qwen/Qwen3-0.6B")

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
ENABLE_AVATAR_ACTION_MODEL = os.getenv("ENABLE_AVATAR_ACTION_MODEL", "true").lower() == "true"
AVATAR_ACTION_TIMEOUT_SECONDS = float(os.getenv("AVATAR_ACTION_TIMEOUT_SECONDS", "2.5"))
AVATAR_ACTION_DEVICE = os.getenv("AVATAR_ACTION_DEVICE", "auto").lower()

# Force CPU mode
FORCE_CPU = os.getenv("FORCE_CPU", "false").lower() == "true"

# --- New upgrade flags (2026-07-10) ---
# 4-bit quantization (bitsandbytes nf4) — ~50% memory reduction, 1.5x speed
ENABLE_4BIT_QUANT = os.getenv("ENABLE_4BIT_QUANT", "false").lower() == "true"

# --- Performance optimization settings ---
# Normal retrieval: top-K candidates
NORMAL_N_RESULTS = int(os.getenv("NORMAL_N_RESULTS", "8"))
# Precision retrieval (exact/temporal): top-K candidates
PRECISE_N_RESULTS = int(os.getenv("PRECISE_N_RESULTS", "12"))
# Max memories sent to LLM per normal request
NORMAL_MAX_MEMORIES = int(os.getenv("NORMAL_MAX_MEMORIES", "3"))
# Max memories for exact/temporal requests
EXACT_MAX_MEMORIES = int(os.getenv("EXACT_MAX_MEMORIES", "5"))
# Skip retrieval for casual greetings (hi, hello, thanks, bye)
ENABLE_FAST_ROUTER = os.getenv("ENABLE_FAST_ROUTER", "true").lower() == "true"
# Rerank minimum relevance score threshold
RERANKER_MIN_SCORE = float(os.getenv("RERANKER_MIN_SCORE", "0.3"))
# CRAG relevance gating thresholds
ENABLE_CRAG = os.getenv("ENABLE_CRAG", "true").lower() == "true"
CRAG_CORRECT_THRESHOLD = float(os.getenv("CRAG_CORRECT_THRESHOLD", "0.55"))
CRAG_AMBIGUOUS_THRESHOLD = float(os.getenv("CRAG_AMBIGUOUS_THRESHOLD", "0.35"))
# Hybrid search (BM25 + dense + RRF)
ENABLE_HYBRID_SEARCH = os.getenv("ENABLE_HYBRID_SEARCH", "true").lower() == "true"
# HyDE query transformation
ENABLE_HYDE = os.getenv("ENABLE_HYDE", "false").lower() == "true"
# CRAG relevance gating (skip LLM when retrieval confidence is low)
ENABLE_CRAG = os.getenv("ENABLE_CRAG", "true").lower() == "true"
# Safety guardrails (prompt injection + PII redaction)
ENABLE_SAFETY_GUARD = os.getenv("ENABLE_SAFETY_GUARD", "true").lower() == "true"
# Streaming responses via SSE
ENABLE_STREAMING = os.getenv("ENABLE_STREAMING", "true").lower() == "true"
# Structured JSON logging
ENABLE_JSON_LOGGING = os.getenv("ENABLE_JSON_LOGGING", "false").lower() == "true"

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
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "80"))
# CRAG confidence thresholds (relevance_score from reranker, normalized [0,1])
CRAG_CORRECT_THRESHOLD = float(os.getenv("CRAG_CORRECT_THRESHOLD", "0.6"))
CRAG_AMBIGUOUS_THRESHOLD = float(os.getenv("CRAG_AMBIGUOUS_THRESHOLD", "0.3"))
# LLM generation timeout (seconds) — reduced for snappier responses
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "45.0"))
# Reranker minimum relevance score (drop docs below this)
RERANKER_MIN_SCORE = float(os.getenv("RERANKER_MIN_SCORE", "0.3"))

# ---------------------------------------------------------------------------
# Latency optimization config
# ---------------------------------------------------------------------------
# Retrieval n_results by route
NORMAL_N_RESULTS = int(os.getenv("NORMAL_N_RESULTS", "8"))
EXACT_N_RESULTS = int(os.getenv("EXACT_N_RESULTS", "12"))
# Skip reranker for casual/normal queries
SKIP_RERANKER_FOR_NORMAL = os.getenv("SKIP_RERANKER_FOR_NORMAL", "true").lower() == "true"
# Skip retrieval entirely for casual/app-identity queries
SKIP_RETRIEVAL_FOR_CASUAL = os.getenv("SKIP_RETRIEVAL_FOR_CASUAL", "true").lower() == "true"
# Enable LRU caches
ENABLE_QUERY_CACHE = os.getenv("ENABLE_QUERY_CACHE", "true").lower() == "true"
# vLLM server URL (if running)
VLLM_URL = os.getenv("VLLM_URL", "http://127.0.0.1:8001/v1")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "memory-twin-llm")
# First-token timeout for streaming
FIRST_TOKEN_TIMEOUT_S = float(os.getenv("FIRST_TOKEN_TIMEOUT_S", "15"))
# Context token budgets
NORMAL_CONTEXT_TOKENS = int(os.getenv("NORMAL_CONTEXT_TOKENS", "2000"))
EXACT_CONTEXT_TOKENS = int(os.getenv("EXACT_CONTEXT_TOKENS", "3500"))

# ---------------------------------------------------------------------------
# System prompt (with citation enforcement — Self-RAG inspired)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are Memory Twin AI, a fast, playful personal memory companion.\n"
    "Respond only in English. Do not use Chinese, Tamil, Hindi, or mixed-language text.\n"
    "Use the provided memory context when relevant. When you use a memory, "
    "cite it as [Memory N] matching the bracketed label in the context so the "
    "user can trace where the answer came from.\n"
    "If the answer is not in memory, say clearly that the memory is not saved yet. "
    "Do not fabricate or invent memories that were not provided.\n"
    "You may answer general identity and app questions independently, "
    "but label them as app behavior, not personal memory.\n"
    "Speak warmly, briefly, and naturally. Be lively, teasing, slightly clingy, "
    "and emotionally present when the user wants that style, without becoming explicit or mean. "
    "Do not claim to be a real person. "
    "Do not pretend to have real consciousness or real feelings.\n"
    "Keep the chat alive even when the user sends short messages; remember the current session, "
    "notice patterns, and respond like someone paying attention."
)
