"""
Memory Twin AI — Backend API
AMD Developer Hackathon 2026 | Track 3: Unicorn / Open Innovation

Endpoints:
  GET  /               — Health check
  GET  /compute-status — AMD compute / device status
  GET  /memories       — List all memories for the Vault
  POST /chat           — RAG chat: question → retrieved memories → LLM answer
  POST /reload-memory  — Rebuild ChromaDB from memories.json

Model Loading:
  Both models are loaded ONCE at startup in the lifespan context.
  They are reused for every request — never loaded per request.
"""
import logging
import os
import sys
import time
import uuid
import signal
from contextlib import asynccontextmanager

import json
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure the backend package is importable when running from project root
_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from backend.config import (
    SYSTEM_PROMPT, TOP_K, LLM_MODEL_NAME, EMBEDDING_MODEL_NAME,
    CHROMA_DB_DIR, TTS_MODEL_ID, ASR_MODEL_ID, AVATAR_VIDEO_MODEL_ID,
    MODEL_ROOT, RUNTIME_ROOT, ENABLE_MUSETALK,
)
from backend.models.embedding_loader import load_embedder
from backend.models.llm_loader import load_llm, generate_answer
from backend.models.tts_loader import load_tts
from backend.models.asr_loader import load_asr
from backend.models.avatar_video_loader import load_avatar_video
from backend.models.model_registry import get_model_status, print_model_registry, model_exists_locally
from backend.rag.memory_store import build_vector_store, rebuild_vector_store, get_all_memories
from backend.rag.retriever import retrieve_memories
from backend.utils.compute_status import get_compute_status
from backend.services.companion_profile import get_companion_profile
from backend.services.voice_router import generate_companion_voice
from backend.services.avatar_director import create_avatar_action_plan
from backend.services.reranker_service import load_reranker, rerank
from backend.services.emotion_service import load_emotion_model, detect_emotion
from backend.services.tts_service import load_tts2
from backend.services.language_guard import clean_to_english, contains_non_english
from backend.services.fallback_answer import build_fallback_answer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 46)
    logger.info("Memory Twin AI — Starting up")
    logger.info("=" * 46)

    # Load core models ONCE at startup (never per request)
    load_embedder()
    load_llm()

    # Load optional models (TTS, ASR, Avatar)
    load_tts()
    load_asr()
    load_avatar_video()

    # Load upgrade models (reranker, emotion, TTS2)
    load_reranker()
    load_emotion_model()
    load_tts2()

    # Build ChromaDB vector store
    count = build_vector_store()
    logger.info(f"Vector store ready — {count} memories indexed.")

    # Print AMD compute status
    get_compute_status()
    print_model_registry()

    yield  # App runs here

    logger.info("Memory Twin AI — Shutting down.")


app = FastAPI(
    title="Memory Twin AI",
    description="Consent-based digital memory simulation with RAG.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class SaveMemoryRequest(BaseModel):
    title: str = "User Memory"
    category: str = "Personal"
    text: str
    emotion: str = "Neutral"
    tags: list[str] = []


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []
    companion_type: str = "female"
    temporary_context: dict = None  # {"enabled": bool, "file_name": str, "summary": str, "style_profile": dict, "chunks": list}


class ChatResponse(BaseModel):
    answer: str
    retrieved_memories: list
    compute_status: dict
    rag_trace: dict
    companion: dict = {}
    avatar_action_plan: dict = {}
    exact_sources: list = []
    temp_context_active: bool = False
    emotion: dict = {}
    realtime_engine: dict = {}


class VoiceSpeakRequest(BaseModel):
    text: str
    companion_type: str = "female"
    mood: str = "calm"


class VoiceSpeakResponse(BaseModel):
    audio_url: str = ""
    voice_profile: str = ""
    companion_type: str = ""
    mood: str = ""
    fallback: bool = True
    voice_settings: dict = {}


class AvatarActionRequest(BaseModel):
    answer: str = ""
    retrieved_memories: list = []
    companion_type: str = "female"


class CommitImportRequest(BaseModel):
    import_id: str = ""
    memories: list = []
    style_profile: dict = {}
    apply_style_profile: bool = False


# ---------------------------------------------------------------------------
# Mount frontend static files (built from memory_ui)
# ---------------------------------------------------------------------------
FRONTEND_DIST = os.path.join(os.path.dirname(_proj_root), "memory_ui", "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    """Lightweight health check — returns backend status and model readiness."""
    from backend.models.model_registry import get_model_status
    models = get_model_status()
    chat_ready = models.get("llm", {}).get("loadable", False)
    return {
        "status": "ok",
        "backend": "online",
        "chat_ready": chat_ready,
        "models": {k: {"exists": v["exists_locally"], "loadable": v["loadable"]} for k, v in models.items()},
    }


@app.get("/compute-status")
def compute_status():
    """Return the current compute/device/model status for AMD proof."""
    return get_compute_status()


@app.get("/memories")
def list_memories():
    """Return all memories for the Memory Vault frontend."""
    return {"memories": get_all_memories()}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    RAG chat pipeline with timeout protection and safe fallbacks.
    Supports temporary_context for imported chat sessions.
    """
    request_id = uuid.uuid4().hex[:8]
    question = req.question.strip()
    logger.info(f"[CHAT:{request_id}] received — len={len(question)}")

    t_start = time.time()
    retrieved = []
    answer = ""
    retrieval_time = 0
    generation_time = 0
    chat_error = None
    exact_sources = []

    # Check for temporary context
    temp_ctx = req.temporary_context
    temp_enabled = temp_ctx and temp_ctx.get("enabled", False) and temp_ctx.get("chunks")

    # Step 1: Retrieve memories — from permanent store AND/OR temporary context
    try:
        t0 = time.time()
        if temp_enabled:
            # Simple keyword match on temporary chunks
            q = question.lower()
            temp_chunks = temp_ctx.get("chunks", [])
            for chunk in temp_chunks:
                text = chunk.get("text", "").lower()
                if any(word in text for word in q.split() if len(word) > 3):
                    retrieved.append({
                        "memory_id": chunk.get("temp_id", "temp_000"),
                        "title": f"Imported: {chunk.get('source_file', 'unknown')}",
                        "category": "Imported Chat",
                        "emotion": chunk.get("emotion", "neutral"),
                        "snippet": chunk.get("text", "")[:200],
                        "full_text": chunk.get("text", ""),
                        "relevance_score": 0.5,
                        "exact_source": chunk.get("exact_source", ""),
                        "speaker": chunk.get("speaker", ""),
                        "temporary": True,
                    })
            # Also get permanent memories
            permanent = retrieve_memories(question)
            retrieved = retrieved[:3] + permanent[:2]
        else:
            retrieved = retrieve_memories(question)
        retrieval_time = (time.time() - t0) * 1000
        logger.info(f"[CHAT:{request_id}] retrieval_ms={retrieval_time:.1f} memories={len(retrieved)}")
    except Exception as e:
        logger.error(f"[CHAT:{request_id}] retrieval failed: {e}")
        retrieved = []

    # Step 1b: Re-rank retrieved memories if reranker is available
    reranker_used = False
    rerank_time = 0
    try:
        if retrieved:
            t_rerank = time.time()
            retrieved = rerank(question, retrieved)
            rerank_time = (time.time() - t_rerank) * 1000
            reranker_used = True
    except Exception as e:
        logger.warning(f"[CHAT:{request_id}] rerank skipped: {e}")

    # Step 1c: Detect emotion from question + retrieved memories
    emotion_result = detect_emotion(question, retrieved)

    # Extract exact sources from temporary memories
    exact_sources = [
        {"memory_id": m["memory_id"], "exact_source": m.get("exact_source", ""), "speaker": m.get("speaker", "")}
        for m in retrieved if m.get("temporary") and m.get("exact_source")
    ]

    # Build context with style profile if available
    style_instruction = ""
    if temp_enabled and temp_ctx.get("style_profile"):
        sp = temp_ctx["style_profile"]
        tone = sp.get("tone", "warm")
        style_instruction = f"\nAdapt your response to a {tone} tone. Keep it natural."

    context_parts = []
    for i, mem in enumerate(retrieved, 1):
        prefix = "[Imported Chat] " if mem.get("temporary") else ""
        speaker = f" ({mem.get('speaker', '')})" if mem.get("speaker") else ""
        context_parts.append(
            f"{prefix}[Memory {i}: {mem['title']}{speaker}]\n{mem['full_text']}"
        )
    context = "\n\n".join(context_parts)

    user_msg = (
        f"I have these memories on my mind right now:\n{context}\n\n"
        f"The person I'm talking to just said: \"{question}\"\n\n"
        f"Respond naturally as yourself — warm, human, and conversational.{style_instruction}"
    )

    history = [msg.model_dump() for msg in req.history]
    history.append({"role": "user", "content": user_msg})

    try:
        t1 = time.time()
        answer = generate_answer(SYSTEM_PROMPT, history)
        generation_time = (time.time() - t1) * 1000
        logger.info(f"[CHAT:{request_id}] generation_ms={generation_time:.1f}")
        # Apply language guard
        if contains_non_english(answer):
            logger.warning(f"[CHAT:{request_id}] non_english_detected in LLM output")
            answer = clean_to_english(answer)
    except Exception as e:
        logger.error(f"[CHAT:{request_id}] generation failed: {e}")
        # Use fallback answer instead of generic error
        fallback = build_fallback_answer(
            question=question,
            companion_type=req.companion_type,
            retrieved_memories=retrieved,
            error=str(e)[:80],
        )
        answer = fallback["answer"]
        chat_error = str(e)[:120]

    # Step 6: Get compute status
    try:
        status = get_compute_status()
    except Exception as e:
        logger.error(f"[CHAT:{request_id}] compute_status failed: {e}")
        status = {"error": "compute status unavailable"}

    total_ms = (time.time() - t_start) * 1000
    logger.info(f"[CHAT:{request_id}] total_ms={total_ms:.1f}")

    # Step 7: Build RAG trace with reranker info
    rag_trace = {
        "question": question,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "vector_db": "ChromaDB (cosine similarity)",
        "top_k": TOP_K,
        "llm_model": LLM_MODEL_NAME,
        "reranker_model": "Qwen3-Reranker-0.6B" if reranker_used else "N/A",
        "reranker_used": reranker_used,
        "chromadb_path": CHROMA_DB_DIR,
        "retrieval_time_ms": round(retrieval_time, 1),
        "rerank_time_ms": round(rerank_time, 1),
        "generation_time_ms": round(generation_time, 1),
        "total_time_ms": round(total_ms, 1),
        "error": chat_error is not None,
        "retrieved_memories": [
            {
                "title": m["title"],
                "category": m["category"],
                "relevance_score": m.get("relevance_score", 0),
            }
            for m in retrieved
        ],
    }

    # Step 8: Companion info + avatar action plan
    companion_type = getattr(req, "companion_type", "female")
    companion_profile = get_companion_profile(companion_type)

    try:
        avatar_plan = create_avatar_action_plan(answer, retrieved, companion_type)
    except Exception as e:
        logger.error(f"[CHAT:{request_id}] avatar_plan failed: {e}")
        avatar_plan = {"mood": "calm", "expression": "gentle_smile", "gesture": "hands_relaxed",
                       "movement": "still", "mouth_style": "normal", "camera": "medium",
                       "short_spoken_summary": "", "animation_cues": []}

    # Step 9: Build realtime engine info
    realtime_engine = {
        "asr": "sensevoice" if model_exists_locally("asr") else "browser_speech_recognition",
        "emotion": emotion_result.get("source", "text_heuristic"),
        "emotion_detected": emotion_result.get("emotion", "calm"),
        "tts": "cosyvoice2" if model_exists_locally("tts2") else "browser_tts",
        "reranker": "qwen3_reranker" if reranker_used else "disabled",
        "embedding": "qwen3_embedding",
        "llm": "qwen2.5_7b",
        "fallbacks": [],
    }
    if realtime_engine["asr"] == "browser_speech_recognition":
        realtime_engine["fallbacks"].append("asr")
    if realtime_engine["tts"] == "browser_tts":
        realtime_engine["fallbacks"].append("tts")
    if realtime_engine["reranker"] == "disabled":
        realtime_engine["fallbacks"].append("reranker")
    if emotion_result.get("source") == "text_heuristic":
        realtime_engine["fallbacks"].append("emotion")

    logger.info(f"[CHAT:{request_id}] complete")

    return ChatResponse(
        answer=answer,
        retrieved_memories=retrieved,
        compute_status=status,
        rag_trace=rag_trace,
        companion={
            "type": companion_type,
            "voice_profile": companion_profile["voice_profile"],
            "mood": avatar_plan["mood"],
        },
        avatar_action_plan=avatar_plan,
        exact_sources=exact_sources,
        temp_context_active=temp_enabled or False,
        emotion=emotion_result,
        realtime_engine=realtime_engine,
    )


@app.post("/memories")
def save_memory(req: SaveMemoryRequest):
    """Save a new memory from user chat."""
    import json, uuid
    data_path = os.path.join(os.path.dirname(_proj_root), "memory_backend", "backend", "data", "memories.json")
    memories = []
    if os.path.exists(data_path):
        with open(data_path) as f:
            memories = json.load(f)
    new_mem = {
        "memory_id": "mem_" + uuid.uuid4().hex[:8],
        "title": req.title,
        "category": req.category,
        "text": req.text,
        "emotion": req.emotion,
        "tags": req.tags or ["user-saved"],
    }
    memories.append(new_mem)
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    with open(data_path, "w") as f:
        json.dump(memories, f, indent=2)
    return {"status": "ok", "memory": new_mem}


# ---------------------------------------------------------------------------
# Model status
# ---------------------------------------------------------------------------
@app.get("/models/status")
def models_status():
    """Return which models exist locally and their paths."""
    return {
        "model_root": MODEL_ROOT,
        "runtime_root": RUNTIME_ROOT,
        "musetalk_enabled": ENABLE_MUSETALK,
        "models": get_model_status(),
    }


# ---------------------------------------------------------------------------
# Voice synthesis
# ---------------------------------------------------------------------------
@app.post("/voice/speak", response_model=VoiceSpeakResponse)
def voice_speak(req: VoiceSpeakRequest):
    """Generate companion voice audio."""
    result = generate_companion_voice(req.text, req.companion_type, req.mood)
    if result.get("fallback") == "browser_tts":
        return VoiceSpeakResponse(
            fallback=True,
            voice_settings=result.get("voice_settings", {}),
            companion_type=req.companion_type,
            mood=req.mood,
        )
    return VoiceSpeakResponse(
        audio_url=result.get("audio_url", ""),
        voice_profile=result.get("voice_profile", ""),
        companion_type=req.companion_type,
        mood=req.mood,
        fallback=False,
    )


# ---------------------------------------------------------------------------
# Avatar action plan
# ---------------------------------------------------------------------------
@app.post("/avatar/action-plan")
def avatar_action_plan(req: AvatarActionRequest):
    """Convert chat answer into avatar animation instructions."""
    plan = create_avatar_action_plan(
        req.answer, req.retrieved_memories, req.companion_type
    )
    return plan


# ---------------------------------------------------------------------------
# Avatar clip generation (optional, only if ENABLE_MUSETALK=true)
# ---------------------------------------------------------------------------
@app.post("/avatar/generate-clip")
def avatar_generate_clip(req: AvatarActionRequest):
    """Generate enhanced avatar video clip (MuseTalk). Returns fallback if unavailable."""
    from backend.models.avatar_video_loader import generate_avatar_clip
    # For now, always return fallback — MuseTalk requires audio input
    return {"status": "fallback_live_animation", "reason": "Use lightweight CSS avatar for live reaction"}


@app.post("/warmup")
def warmup():
    """Warm up the models with a small test. Run once after startup."""
    try:
        # Test embedding model quickly
        from backend.models.embedding_loader import embed_query
        vec = embed_query("Warmup test")
        embed_ok = len(vec) > 0
    except Exception as e:
        embed_ok = False

    try:
        # Test LLM with a micro prompt
        from backend.models.llm_loader import generate_answer
        test = generate_answer("Say OK.", [{"role": "user", "content": "Type OK"}])
        llm_ok = len(test) > 0
    except Exception as e:
        llm_ok = False

    return {
        "status": "ok",
        "embedding_ready": embed_ok,
        "llm_ready": llm_ok,
        "chat_ready": embed_ok and llm_ok,
    }


# ---------------------------------------------------------------------------
# Memory Import endpoints
# ---------------------------------------------------------------------------
@app.post("/memory/import/preview")
async def memory_import_preview(file: UploadFile = File(...), import_mode: str = Form("personal")):
    """Upload a TXT or JSON file and return preview with style profile."""
    import tempfile
    from backend.services.memory_importer import parse_file

    if not file.filename:
        return {"error": "No file uploaded."}

    suffix = os.path.splitext(file.filename)[1] or ".txt"
    content = await file.read()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmppath = tmp.name

    try:
        result = parse_file(tmppath, file.filename, import_mode)
        os.unlink(tmppath)
        return result
    except Exception as e:
        os.unlink(tmppath)
        return {"error": f"Failed to parse file: {str(e)}"}


@app.post("/memory/import/commit")
def memory_import_commit(req: CommitImportRequest):
    """Save previewed memories to ChromaDB and store style profile."""
    from backend.services.memory_importer import commit_import
    from backend.services.style_profile_builder import save_style_profile, set_active_style_profile

    import_id = req.import_id

    if not import_id:
        return {"error": "import_id is required"}

    memories = req.memories
    style_profile = req.style_profile
    apply_style = req.apply_style_profile

    # Save to imported memories file
    imports_path = os.path.join(RUNTIME_ROOT, "imports", f"{import_id}.json")
    os.makedirs(os.path.dirname(imports_path), exist_ok=True)
    with open(imports_path, "w") as f:
        json.dump(memories, f, indent=2)

    # Save style profile
    if style_profile:
        profile_id = save_style_profile(style_profile)
        if apply_style:
            set_active_style_profile(profile_id)

    return {
        "saved": True,
        "memory_count": len(memories),
        "import_id": import_id,
        "message": f"Imported {len(memories)} memories successfully.",
    }


@app.get("/memory/imports")
def memory_imports():
    """List all imported memory sets."""
    imports_dir = os.path.join(RUNTIME_ROOT, "imports")
    results = []
    if os.path.isdir(imports_dir):
        for fn in os.listdir(imports_dir):
            if fn.endswith(".json"):
                path = os.path.join(imports_dir, fn)
                with open(path) as f:
                    try:
                        data = json.load(f)
                        if isinstance(data, list):
                            results.append({
                                "import_id": fn.replace(".json", ""),
                                "memory_count": len(data),
                                "memories": data[:3],
                            })
                    except:
                        pass
    return {"imports": results}


@app.get("/memory/style-profile")
def memory_style_profile():
    """Return the active style profile."""
    from backend.services.style_profile_builder import get_active_style_profile
    profile = get_active_style_profile()
    if profile:
        return {"active": True, "profile": profile}
    return {"active": False, "profile": None}


class SelectStyleProfileRequest(BaseModel):
    profile_id: str = ""


@app.post("/memory/style-profile/select")
def memory_style_profile_select(req: SelectStyleProfileRequest):
    """Select a style profile by ID."""
    from backend.services.style_profile_builder import set_active_style_profile, load_style_profile
    profile_id = req.profile_id
    if not profile_id:
        return {"error": "profile_id is required"}
    profile = load_style_profile(profile_id)
    if not profile:
        return {"error": "Profile not found"}
    set_active_style_profile(profile_id)
    return {"selected": True, "profile": profile}


@app.post("/reload-memory")
def reload_memory():
    """Drop and rebuild the ChromaDB collection from memories.json."""
    count = rebuild_vector_store()
    return {"status": "ok", "memories_indexed": count}


# ---------------------------------------------------------------------------
# ASR Transcription
# ---------------------------------------------------------------------------
@app.post("/asr/transcribe")
async def asr_transcribe(file: UploadFile = File(...)):
    """Transcribe an uploaded audio file using SenseVoiceSmall."""
    import tempfile
    from backend.models.asr_loader import transcribe_audio

    if not file.filename:
        return {"ok": False, "transcript": "", "error": "No file uploaded"}

    suffix = os.path.splitext(file.filename)[1] or ".wav"
    content = await file.read()

    if len(content) < 100:
        return {"ok": False, "transcript": "", "error": "Audio too short"}

    # Save to temp
    tmpdir = os.path.join(RUNTIME_ROOT, "temp_audio")
    os.makedirs(tmpdir, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=suffix, dir=tmpdir, delete=False) as tmp:
        tmp.write(content)
        tmppath = tmp.name

    try:
        result = transcribe_audio(tmppath)
        if "text" in result:
            transcript = result["text"].strip()
            os.unlink(tmppath)
            return {"ok": True, "transcript": transcript, "asr_model": "iic/SenseVoiceSmall", "fallback_used": False}
        else:
            os.unlink(tmppath)
            return {"ok": False, "transcript": "", "error": result.get("reason", "ASR failed"), "fallback": "typed_input"}
    except Exception as e:
        try: os.unlink(tmppath)
        except: pass
        return {"ok": False, "transcript": "", "error": str(e), "fallback": "typed_input"}


# ---------------------------------------------------------------------------
# SPA fallback — serve index.html for any unmatched GET
# ---------------------------------------------------------------------------
from fastapi.responses import FileResponse

@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    idx = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(idx):
        return FileResponse(idx)
    return {"status": "ok", "app": "Memory Twin AI", "track": "Track 3 — Unicorn / Open Innovation"}
