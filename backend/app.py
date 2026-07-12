"""
Memory Twin AI — Backend API
AMD Developer Hackathon 2026 | Track 3: Unicorn / Open Innovation

Minimal reliable backend serving the frontend + /chat + import endpoints.
"""
import asyncio
import json
import logging
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from enum import Enum
from typing import Optional

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from backend.config import (SYSTEM_PROMPT, TOP_K, LLM_MODEL_NAME, EMBEDDING_MODEL_NAME, CHROMA_DB_DIR,
                           MODEL_ROOT, LLM_TIMEOUT_SECONDS, AVATAR_ACTION_TIMEOUT_SECONDS)
from backend.models.embedding_loader import load_embedder
from backend.models.llm_loader import load_llm, generate_answer
from backend.models.tts_loader import load_tts
from backend.models.asr_loader import load_asr
from backend.models.model_registry import get_model_status, print_model_registry
from backend.rag.memory_store import build_vector_store, rebuild_vector_store, get_all_memories
from backend.rag.retriever import retrieve_memories
from backend.utils.compute_status import get_compute_status
from backend.services.avatar_director import create_avatar_action_plan, create_model_avatar_action_plan
from backend.services.companion_profile import get_companion_profile
from backend.services.language_guard import contains_non_english, clean_to_english
from backend.services.fallback_answer import build_fallback_answer
from backend.services.fast_query_router import route_query, CASUAL, APP_IDENTITY, NORMAL_MEMORY, EXACT_MEMORY
from backend.services.streaming_llm_service import stream_chat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 46)
    logger.info("Memory Twin AI — Starting up")
    logger.info("=" * 46)
    from backend.core.service_container import ServiceContainer
    container = ServiceContainer.get()

    embedder = load_embedder()
    container.embedder_model = embedder

    llm_model, llm_tokenizer = load_llm()
    container.llm_model = llm_model
    container.llm_tokenizer = llm_tokenizer

    try:
        from backend.models.avatar_action_loader import load_avatar_action_model
        action_model, action_tokenizer = load_avatar_action_model()
        container.avatar_action_model = action_model
        container.avatar_action_tokenizer = action_tokenizer
    except Exception as exc:
        logger.warning("Avatar action model unavailable; instant rules remain active: %s", exc)

    load_tts()
    load_asr()
    count = build_vector_store()
    container.chroma_collection = None  # Will be set on first retrieval
    logger.info(f"Vector store ready — {count} memories indexed.")
    get_compute_status()
    print_model_registry()
    yield

# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------
class ErrorCode(str, Enum):
    CHAT_TIMEOUT = "CHAT_TIMEOUT"
    CHAT_CANCELLED = "CHAT_CANCELLED"
    CHAT_GENERATION_FAILED = "CHAT_GENERATION_FAILED"
    BACKEND_UNREACHABLE = "BACKEND_UNREACHABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    MODEL_NOT_LOADED = "MODEL_NOT_LOADED"
    INVALID_REQUEST = "INVALID_REQUEST"
    ASR_UNAVAILABLE = "ASR_UNAVAILABLE"
    ASR_TIMEOUT = "ASR_TIMEOUT"
    ASR_CANCELLED = "ASR_CANCELLED"
    TTS_UNAVAILABLE = "TTS_UNAVAILABLE"
    TTS_CANCELLED = "TTS_CANCELLED"
    MEMORY_SAVE_FAILED = "MEMORY_SAVE_FAILED"
    MEMORY_VALIDATION_FAILED = "MEMORY_VALIDATION_FAILED"
    QUEUE_FULL = "QUEUE_FULL"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_RETRYABLE_ERRORS = {
    ErrorCode.CHAT_TIMEOUT,
    ErrorCode.CHAT_GENERATION_FAILED,
    ErrorCode.ASR_TIMEOUT,
    ErrorCode.MODEL_UNAVAILABLE,
    ErrorCode.RETRIEVAL_FAILED,
    ErrorCode.MEMORY_SAVE_FAILED,
    ErrorCode.INTERNAL_ERROR,
}


def make_error(code, message: str, **extra) -> dict:
    """Build a structured error dict matching the backend error contract.
    
    Accepts both ErrorCode enum values and plain strings.
    """
    code_str = code.value if isinstance(code, ErrorCode) else str(code)
    return {
        "ok": False,
        "error_code": code_str,
        "error": message,
        **extra,
    }


# ---------------------------------------------------------------------------
# Concurrency semaphores — limit concurrent GPU workloads
# ---------------------------------------------------------------------------
_LLM_SEMAPHORE = asyncio.Semaphore(1)
_EMBED_SEMAPHORE = asyncio.Semaphore(1)
_ASR_SEMAPHORE = asyncio.Semaphore(1)
_TTS_SEMAPHORE = asyncio.Semaphore(1)
_AVATAR_ACTION_SEMAPHORE = asyncio.Semaphore(1)

_LLM_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm")
_AVATAR_ACTION_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="avatar-action")


# ---------------------------------------------------------------------------
# Request lifecycle tracking
# ---------------------------------------------------------------------------
_active_requests: dict[str, float] = {}
_request_lock = threading.Lock()


def register_request(request_id: str, path: str = "/chat") -> None:
    with _request_lock:
        _active_requests[request_id] = {"started_at": time.time(), "path": path}


def complete_request(request_id: str) -> None:
    with _request_lock:
        _active_requests.pop(request_id, None)


def cancel_request(request_id: str) -> None:
    with _request_lock:
        _active_requests.pop(request_id, None)


def get_active_request_count() -> int:
    return len(_active_requests)


app = FastAPI(title="Memory Twin AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Serve built frontend
FRONTEND_DIST = os.path.join(_proj_root, "frontend", "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

# Serve VAD assets from backend too — so dev tunnels proxying port 8000
# can still load the WASM/ONNX files needed by @ricky0123/vad-web.
# This is critical when the frontend is accessed via a tunnel that only
# proxies the backend port (e.g. https://xxx-8000.devtunnels.ms).
VAD_ASSETS_DIR = os.path.join(_proj_root, "frontend", "public", "vad-assets")
if os.path.isdir(VAD_ASSETS_DIR):
    app.mount("/vad-assets", StaticFiles(directory=VAD_ASSETS_DIR), name="vad-assets")
    logger.info(f"VAD assets served from {VAD_ASSETS_DIR}")

# ── Schemas ────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str
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
    temporary_context: dict = None
    voice_mode: bool = False

class ChatResponse(BaseModel):
    answer: str
    retrieved_memories: list
    compute_status: dict
    rag_trace: dict
    companion: dict = {}
    avatar_action_plan: dict = {}
    emotion: dict = {}

class AvatarActionRequest(BaseModel):
    answer: str
    retrieved_memories: list[dict] = []
    companion_type: str = "female"

# ── Endpoints ──────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "backend": "online", "chat_ready": True}

@app.get("/compute")
def compute():
    return get_compute_status()

@app.get("/compute-status")
def compute_status():
    return get_compute_status()

@app.post("/avatar/action")
async def avatar_action(req: AvatarActionRequest):
    """Return optional model-refined motion without delaying chat or speech."""
    answer = req.answer.strip()[:1200]
    companion_type = "male" if req.companion_type == "male" else "female"
    base_plan = create_avatar_action_plan(
        answer,
        req.retrieved_memories[:3],
        companion_type,
    )
    loop = asyncio.get_running_loop()
    try:
        async with _AVATAR_ACTION_SEMAPHORE:
            plan = await asyncio.wait_for(
                loop.run_in_executor(
                    _AVATAR_ACTION_EXECUTOR,
                    create_model_avatar_action_plan,
                    answer,
                    req.retrieved_memories[:3],
                    companion_type,
                    base_plan,
                ),
                timeout=AVATAR_ACTION_TIMEOUT_SECONDS,
            )
    except asyncio.TimeoutError:
        logger.info("Avatar action refinement exceeded %.1fs; using instant rules.", AVATAR_ACTION_TIMEOUT_SECONDS)
        plan = {**base_plan, "director": "instant_rules", "director_timeout": True}
    except Exception as exc:
        logger.warning("Avatar action refinement failed: %s", exc)
        plan = {**base_plan, "director": "instant_rules", "director_error": True}

    return {"ok": True, "plan": plan}

@app.get("/memories")
def list_memories():
    return {"memories": get_all_memories()}

@app.post("/memories")
def save_memory(req: SaveMemoryRequest):
    """Save a new memory to the vault and incrementally index it in ChromaDB."""
    from backend.services.auto_memory_extractor import _is_dangerous_input, _sanitize_text

    text = _sanitize_text(req.text, max_length=1000)
    title = _sanitize_text(req.title, max_length=200)
    category = _sanitize_text(req.category, max_length=100)
    emotion = _sanitize_text(req.emotion, max_length=50)
    tags = [t.strip()[:50] for t in req.tags[:10]]

    if not text:
        return {"ok": False, "error": "Memory text is required", "saved": False, "memory_id": None}

    if _is_dangerous_input(text):
        logger.warning(f"[MEMORIES] Rejected dangerous input: {text[:80]}")
        return {"ok": False, "error": "Input validation failed", "saved": False, "memory_id": None}

    try:
        # Load existing memories
        memories_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "memories.json")
        if os.path.exists(memories_path):
            with open(memories_path, "r") as f:
                memories = json.load(f)
        else:
            memories = []

        # Generate unique memory_id
        existing_ids = {m.get("memory_id", "") for m in memories}
        idx = 1
        while f"manual_{idx:04d}" in existing_ids:
            idx += 1
        memory_id = f"manual_{idx:04d}"

        from datetime import datetime as _dt
        entry = {
            "memory_id": memory_id,
            "title": title,
            "text": text,
            "category": category,
            "emotion": emotion,
            "tags": tags,
            "source": "manual",
            "created_at": _dt.utcnow().isoformat() + "Z",
        }
        memories.append(entry)

        # Atomic write to JSON file
        import tempfile as _tf
        fd, tmp = _tf.mkstemp(suffix=".json", dir=os.path.dirname(memories_path))
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(memories, f, indent=2)
            os.replace(tmp, memories_path)
        except:
            os.unlink(tmp)
            raise

        # Incremental ChromaDB upsert
        indexed = False
        try:
            from backend.rag.memory_store import _get_collection
            collection = _get_collection()

            from backend.core.service_container import ServiceContainer
            container = ServiceContainer.get()

            if container.embedder_model is not None:
                embedding = container.embedder_model.encode(
                    [text], prompt_name="query", convert_to_numpy=True
                ).tolist()[0]
            else:
                from backend.models.embedding_loader import embed_documents
                embedding = embed_documents([text])[0]

            collection.upsert(
                ids=[memory_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[{
                    "memory_id": memory_id,
                    "title": title,
                    "category": category,
                    "emotion": emotion,
                    "tags": ", ".join(tags),
                }],
            )
            container.bump_memory_version()
            indexed = True
        except Exception as e:
            logger.warning(f"[MEMORIES] ChromaDB upsert failed: {e}")

        logger.info(f"[MEMORIES] Saved {memory_id}: {title}")
        return {
            "ok": True,
            "memory_id": memory_id,
            "memory": entry,
            "indexed": indexed,
        }
    except Exception as e:
        logger.error(f"[MEMORIES] Save failed: {e}")
        return {"ok": False, "error": str(e)[:200], "saved": False, "memory_id": None}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    request_id = uuid.uuid4().hex[:8]
    question = req.question.strip()
    logger.info(f"[CHAT:{request_id}] received: {question[:80]}")

    register_request(request_id, "/chat")
    t_start = time.time()
    retrieved = []
    answer = ""
    retrieval_time = 0
    generation_time = 0
    route_ms = 0
    route = NORMAL_MEMORY
    route_meta = {}

    try:
        # Step 0a: Auto-extract memory from user message (e.g., "remember that...")
        try:
            from services.auto_memory_extractor import check_and_extract
            auto_mem_id = check_and_extract(question)
            if auto_mem_id:
                logger.info(f"[CHAT:{request_id}] auto-saved memory {auto_mem_id}")
        except Exception as e:
            logger.warning(f"[CHAT:{request_id}] auto-memory extraction failed: {e}")

        # Step 0b: Fast route classification (no LLM)
        try:
            t_route = time.time()
            history_dicts = [msg.model_dump() for msg in req.history]
            route, route_meta = route_query(question, history_dicts)
            route_ms = (time.time() - t_route) * 1000
            logger.info(f"[CHAT:{request_id}] route={route} reason={route_meta.get('reason')} route_ms={route_ms:.1f}")
        except Exception as e:
            logger.warning(f"[CHAT:{request_id}] routing failed: {e}")
            route = NORMAL_MEMORY
            route_meta = {"skip_retrieval": False, "use_reranker": False, "n_results": 5}

        # Step 1: Retrieval (skip for casual/app-identity)
        if not route_meta.get("skip_retrieval", False):
            try:
                t0 = time.time()
                n_results = route_meta.get("n_results", 5)
                retrieved = retrieve_memories(question, n_results=n_results)
                retrieval_time = (time.time() - t0) * 1000
                logger.info(f"[CHAT:{request_id}] retrieval_ms={retrieval_time:.1f} memories={len(retrieved)}")
            except Exception as e:
                logger.error(f"[CHAT:{request_id}] retrieval failed: {e}")
                retrieved = []

        # Step 1.5: Check for trigger rule match
        trigger_match = None
        try:
            from rag.retriever import match_trigger_rule
            trigger_match = match_trigger_rule(question)
            if trigger_match:
                logger.info(f"[CHAT:{request_id}] trigger_rule matched: {trigger_match.get('trigger')}")
                retrieved = [trigger_match] + retrieved
        except Exception as e:
            logger.warning(f"[CHAT:{request_id}] trigger check failed: {e}")

        # Step 2: Build prompt
        context_parts = []
        char_limit = 500 if route == NORMAL_MEMORY else 800
        for i, mem in enumerate(retrieved[:3], 1):
            text = mem['full_text'][:char_limit]
            context_parts.append(f"[Memory {i}: {mem['title']} ({mem['category']})]\n{text}")
        context = "\n\n".join(context_parts) if context_parts else "(no relevant memories found)"

        rule_instruction = ""
        if trigger_match and trigger_match.get("response"):
            rule_instruction = f"\n\nIMPORTANT RULE: When the user says \"{trigger_match['trigger']}\", you MUST respond: {trigger_match['response']}"

        temp_context_section = _build_temp_context_section(req.temporary_context)

        response_style = _voice_response_style() if req.voice_mode else "Respond warmly and briefly."
        user_msg = f"Relevant memories:\n{context}\n\nUser: {question}\n\n{response_style}{rule_instruction}{temp_context_section}"

        history = [msg.model_dump() for msg in req.history[-6:]]
        history.append({"role": "user", "content": user_msg})

        # Step 3: Generate with concurrency control and timeout
        try:
            t1 = time.time()
            loop = asyncio.get_running_loop()
            async with _LLM_SEMAPHORE:
                answer = await asyncio.wait_for(
                    loop.run_in_executor(_LLM_EXECUTOR, generate_answer, SYSTEM_PROMPT, history),
                    timeout=LLM_TIMEOUT_SECONDS,
                )
            generation_time = (time.time() - t1) * 1000
            if contains_non_english(answer):
                answer = clean_to_english(answer)
            logger.info(f"[CHAT:{request_id}] generation_ms={generation_time:.1f}")
        except asyncio.TimeoutError:
            logger.error(f"[CHAT:{request_id}] generation timed out after {LLM_TIMEOUT_SECONDS}s")
            fallback = build_fallback_answer(question=question, retrieved_memories=retrieved,
                                             error=f"Response timed out after {LLM_TIMEOUT_SECONDS}s")
            answer = fallback["answer"]
        except asyncio.CancelledError:
            logger.info(f"[CHAT:{request_id}] generation cancelled")
            cancel_request(request_id)
            return make_error(ErrorCode.CHAT_CANCELLED, "Request was cancelled")
        except Exception as e:
            logger.error(f"[CHAT:{request_id}] generation failed: {e}")
            fallback = build_fallback_answer(question=question, retrieved_memories=retrieved, error=str(e)[:80])
            answer = fallback["answer"]

        total_ms = (time.time() - t_start) * 1000
        status = get_compute_status()

        rag_trace = {
            "question": question,
            "embedding_model": EMBEDDING_MODEL_NAME,
            "llm_model": LLM_MODEL_NAME,
            "route": route,
            "route_ms": round(route_ms, 1),
            "retrieval_time_ms": round(retrieval_time, 1),
            "generation_time_ms": round(generation_time, 1),
            "total_time_ms": round(total_ms, 1),
            "skip_retrieval": route_meta.get("skip_retrieval", False),
            "reranker_reason": route_meta.get("reason", ""),
            "trigger_matched": trigger_match.get("trigger") if trigger_match else None,
            "retrieved_memories": [{"title": m["title"], "category": m["category"], "relevance_score": m.get("relevance_score", 0)} for m in retrieved[:3]],
        }

        profile = get_companion_profile(req.companion_type)
        avatar_plan = create_avatar_action_plan(answer, retrieved, req.companion_type)

        return ChatResponse(
            answer=answer,
            retrieved_memories=retrieved[:3],
            compute_status=status,
            rag_trace=rag_trace,
            companion={"type": req.companion_type, "voice_profile": profile["voice_profile"], "mood": avatar_plan["mood"]},
            avatar_action_plan=avatar_plan,
            emotion={"emotion": avatar_plan["mood"], "source": "avatar_action_plan"},
        )
    except Exception as e:
        logger.error(f"[CHAT:{request_id}] unexpected error: {e}")
        return make_error(ErrorCode.INTERNAL_ERROR, str(e)[:200])
    finally:
        complete_request(request_id)

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE streaming endpoint — emits events as they happen."""
    from fastapi.responses import StreamingResponse

    request_id = uuid.uuid4().hex[:8]
    question = req.question.strip()
    logger.info(f"[STREAM:{request_id}] received: {question[:80]}")

    # Auto-extract memory from user message (e.g., "remember that...")
    try:
        from services.auto_memory_extractor import check_and_extract
        auto_mem_id = check_and_extract(question)
        if auto_mem_id:
            logger.info(f"[STREAM:{request_id}] auto-saved memory {auto_mem_id}")
    except Exception as e:
        logger.warning(f"[STREAM:{request_id}] auto-memory extraction failed: {e}")

    async def event_generator():
        t_start = time.time()
        try:
            # 1. Route
            history_dicts = [msg.model_dump() for msg in req.history]
            route, route_meta = route_query(question, history_dicts)
            yield f"data: {json.dumps({'type': 'chat.accepted', 'request_id': request_id, 'route': route})}\n\n"

            # 2. Retrieval (skip for casual)
            retrieved = []
            if not route_meta.get("skip_retrieval", False):
                yield f"data: {json.dumps({'type': 'retrieval.started'})}\n\n"
                t0 = time.time()
                n_results = route_meta.get("n_results", 5)
                retrieved = retrieve_memories(question, n_results=n_results)
                retrieval_ms = (time.time() - t0) * 1000
                yield f"data: {json.dumps({'type': 'retrieval.completed', 'count': len(retrieved), 'ms': round(retrieval_ms, 1)})}\n\n"

            # 2.5: Check for trigger rule match (e.g., "if I say 22, tell me I'm beautiful")
            trigger_match = None
            try:
                from rag.retriever import match_trigger_rule
                trigger_match = match_trigger_rule(question)
                if trigger_match:
                    logger.info(f"[STREAM:{request_id}] trigger_rule matched: {trigger_match.get('trigger')}")
                    retrieved = [trigger_match] + retrieved
            except Exception as e:
                logger.warning(f"[STREAM:{request_id}] trigger check failed: {e}")

            # 3. Build prompt
            context_parts = []
            char_limit = 500 if route == NORMAL_MEMORY else 800
            for i, mem in enumerate(retrieved[:3], 1):
                text = mem['full_text'][:char_limit]
                context_parts.append(f"[Memory {i}: {mem['title']} ({mem['category']})]\n{text}")
            context = "\n\n".join(context_parts) if context_parts else "(no relevant memories found)"

            # If a trigger rule matched, add explicit instruction
            rule_instruction = ""
            if trigger_match and trigger_match.get("response"):
                rule_instruction = f"\n\nIMPORTANT RULE: When the user says \"{trigger_match['trigger']}\", you MUST respond: {trigger_match['response']}"

            # Inject temporary imported context (e.g., WhatsApp chat) into the prompt
            temp_context_section = _build_temp_context_section(req.temporary_context)

            response_style = _voice_response_style() if req.voice_mode else "Respond warmly and briefly."
            user_msg = f"Relevant memories:\n{context}\n\nUser: {question}\n\n{response_style}{rule_instruction}{temp_context_section}"
            messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_msg}]

            # 4. Stream LLM — adaptive max_new_tokens based on route
            yield f"data: {json.dumps({'type': 'answer.first_token'})}\n\n"
            full_answer = ""
            t_llm = time.time()
            # Casual queries get fewer tokens (faster), memory queries get more
            if req.voice_mode:
                max_tokens = 36 if route == CASUAL else (70 if route == EXACT_MEMORY else 55)
            else:
                max_tokens = 40 if route == CASUAL else (120 if route == EXACT_MEMORY else 80)
            async for token in stream_chat(messages, max_new_tokens=max_tokens, temperature=0.7):
                full_answer += token
                yield f"data: {json.dumps({'type': 'answer.delta', 'delta': token})}\n\n"
                # Early stop on common end patterns
                if full_answer.rstrip().endswith(('.', '!', '?', '."', '!"', '?"')) and len(full_answer) > 20:
                    # Check if we have a complete sentence
                    if len(full_answer) > 40:
                        break
            llm_ms = (time.time() - t_llm) * 1000

            # 5. Avatar action plan and done
            avatar_plan = create_avatar_action_plan(full_answer, retrieved[:3], req.companion_type)
            yield f"data: {json.dumps({'type': 'avatar.action', 'plan': avatar_plan})}\n\n"
            total_ms = (time.time() - t_start) * 1000
            yield f"data: {json.dumps({'type': 'answer.completed', 'answer': full_answer, 'llm_ms': round(llm_ms, 1), 'total_ms': round(total_ms, 1), 'retrieved_memories': retrieved[:3], 'avatar_action_plan': avatar_plan})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"[STREAM:{request_id}] error: {e}")
            yield f"data: {json.dumps({'type': 'chat.error', 'error': str(e)[:200]})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/reload-memory")
def reload_memory():
    count = rebuild_vector_store()
    return {"status": "ok", "memories_indexed": count}


# ── Import endpoint (WhatsApp TXT / JSON) ──────────────────────────
@app.post("/memory/import/preview")
async def memory_import_preview(file: UploadFile = File(...)):
    """
    Parse an uploaded WhatsApp TXT or JSON file into per-message records.
    Returns session_id, messages, and a quick summary for the temp context panel.
    """
    from fastapi import UploadFile, File
    from backend.services.memory_importer import parse_file_to_messages

    try:
        # Save uploaded file to a temp location
        import tempfile
        suffix = os.path.splitext(file.filename or "chat.txt")[1] or ".txt"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Parse using existing importer
        result = parse_file_to_messages(tmp_path, file.filename or "chat.txt")

        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        # Build a quick summary from the messages
        messages = result.get("messages", [])
        summary = _build_import_summary(messages)
        tone = _detect_tone(messages)
        emotions = _detect_emotions(messages)

        return {
            "session_id": result.get("session_id"),
            "file_name": result.get("file_name"),
            "file_type": result.get("file_type"),
            "message_count": len(messages),
            "messages": messages[:200],  # Cap at 200 for preview
            "summary": summary,
            "tone": tone,
            "emotions": emotions,
        }
    except Exception as e:
        logger.error(f"[IMPORT] failed: {e}")
        return {"error": str(e)[:200], "messages": []}


def _build_import_summary(messages: list) -> str:
    """Build a short summary from imported messages."""
    if not messages:
        return "Empty chat"
    speakers = set()
    for m in messages[:50]:
        s = m.get("speaker", "")
        if s:
            speakers.add(s)
    speaker_list = ", ".join(sorted(speakers)[:5]) if speakers else "unknown"
    return f"{len(messages)} messages from {speaker_list}"


def _detect_tone(messages: list) -> str:
    """Detect overall tone from message content."""
    if not messages:
        return "neutral"
    text = " ".join(m.get("text", "") for m in messages[:30]).lower()
    # Simple keyword-based tone detection
    warm_words = ["love", "miss", "dear", "sweet", "honey", "beautiful", "❤️", "💕", "😊", "🥰"]
    playful_words = ["haha", "lol", "😂", "🤣", "funny", "joke"]
    serious_words = ["important", "serious", "urgent", "please", "sorry"]
    warm = sum(1 for w in warm_words if w in text)
    playful = sum(1 for w in playful_words if w in text)
    serious = sum(1 for w in serious_words if w in text)
    if warm >= playful and warm >= serious and warm > 0:
        return "warm"
    if playful > warm and playful > serious:
        return "playful"
    if serious > warm and serious > playful:
        return "serious"
    return "neutral"


def _detect_emotions(messages: list) -> list:
    """Detect dominant emotions from message content."""
    if not messages:
        return []
    text = " ".join(m.get("text", "") for m in messages[:30]).lower()
    emotions = []
    if any(w in text for w in ["love", "miss", "❤️", "💕", "dear"]):
        emotions.append("love")
    if any(w in text for w in ["happy", "glad", "great", "😊", "🎉", "awesome"]):
        emotions.append("joy")
    if any(w in text for w in ["sad", "sorry", "miss you", "😢", "cry"]):
        emotions.append("sadness")
    if any(w in text for w in ["angry", "mad", "furious", "😠", "hate"]):
        emotions.append("anger")
    if any(w in text for w in ["funny", "haha", "lol", "😂", "joke"]):
        emotions.append("humor")
    return emotions or ["neutral"]


def _voice_response_style() -> str:
    return (
        "You are speaking in a live voice call. "
        "Reply immediately in one or two short natural sentences. "
        "Do not use markdown, headings, lists, citations, or formal assistant phrases. "
        "Do not repeat the user's full question. "
        "Use contractions and ask at most one question."
    )


# ── Helper: build temp context prompt section ──────────────────────
def _build_temp_context_section(temp_ctx: dict) -> str:
    """Build a prompt section from temporary_context (imported chat)."""
    if not temp_ctx:
        return ""
    file_name = temp_ctx.get("file_name", "imported chat")
    summary = temp_ctx.get("summary", "")
    style = temp_ctx.get("style_profile", {})
    chunks = temp_ctx.get("chunks", [])

    parts = [f"\n\n--- TEMPORARY IMPORTED CONTEXT ({file_name}) ---"]
    if summary:
        parts.append(f"Summary: {summary}")
    if style.get("tone"):
        parts.append(f"Tone: {style['tone']}")
    if style.get("emotions"):
        parts.append(f"Emotions: {', '.join(style['emotions'])}")
    if chunks:
        parts.append("\nRelevant messages from the imported chat:")
        # Include up to 5 most relevant chunks (or first 5 if no scores)
        sorted_chunks = sorted(chunks, key=lambda c: c.get("relevance", 0), reverse=True)
        for i, chunk in enumerate(sorted_chunks[:5], 1):
            speaker = chunk.get("speaker", "Unknown")
            text = chunk.get("text", "")[:300]
            date = chunk.get("date", "")
            parts.append(f"  [{i}] {speaker}" + (f" ({date})" if date else "") + f": {text}")
    parts.append("--- END TEMPORARY CONTEXT ---\n")
    parts.append("IMPORTANT: When answering, prioritize facts from the temporary imported context above. "
                 "If the user asks about something from the imported chat, answer based on those messages.")
    return "\n".join(parts)

# SPA fallback
@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    idx = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(idx):
        return FileResponse(idx)
    return {"status": "ok", "app": "Memory Twin AI", "track": "Track 3 — Unicorn / Open Innovation"}
