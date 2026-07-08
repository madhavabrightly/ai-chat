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
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure the backend package is importable when running from project root
_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from backend.config import SYSTEM_PROMPT
from backend.models.embedding_loader import load_embedder
from backend.models.llm_loader import load_llm, generate_answer
from backend.rag.memory_store import build_vector_store, rebuild_vector_store, get_all_memories
from backend.rag.retriever import retrieve_memories
from backend.utils.compute_status import get_compute_status

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

    # Load models ONCE at startup (never per request)
    load_embedder()
    load_llm()

    # Build ChromaDB vector store
    count = build_vector_store()
    logger.info(f"Vector store ready — {count} memories indexed.")

    # Print AMD compute status
    get_compute_status()

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
class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    retrieved_memories: list
    compute_status: dict


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
    return {"status": "ok", "app": "Memory Twin AI", "track": "Track 3 — Unicorn / Open Innovation"}


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
    RAG chat pipeline:
      1. Embed question → retrieve top-K memories from ChromaDB
      2. Build memory context string
      3. Send system prompt + context + question to LLM
      4. Return answer + retrieved memories + compute status
    """
    question = req.question.strip()
    logger.info(f"Chat request received: {question[:100]}...")

    # Step 1: Retrieve relevant memories
    retrieved = retrieve_memories(question)

    # Step 2: Build context from retrieved memories
    context_parts = []
    for i, mem in enumerate(retrieved, 1):
        context_parts.append(
            f"[Memory {i}: {mem['title']} ({mem['category']})]\n{mem['full_text']}"
        )
    context = "\n\n".join(context_parts)

    # Step 3: Build the user prompt (context + question)
    user_prompt = (
        f"Here are relevant memories:\n{context}\n\n"
        f"User's question: {question}\n\n"
        f"Please answer warmly using the memories above."
    )

    # Step 4: Generate answer
    answer = generate_answer(SYSTEM_PROMPT, user_prompt)

    # Step 5: Get compute status
    status = get_compute_status()

    return ChatResponse(
        answer=answer,
        retrieved_memories=retrieved,
        compute_status=status,
    )


@app.post("/reload-memory")
def reload_memory():
    """Drop and rebuild the ChromaDB collection from memories.json."""
    count = rebuild_vector_store()
    return {"status": "ok", "memories_indexed": count}


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
