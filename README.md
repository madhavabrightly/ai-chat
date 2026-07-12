# Memory Twin AI

**AMD Developer Hackathon 2026 — Track 3: Unicorn / Open Innovation**

An AI-powered digital memory twin that stores fictional personal memories, retrieves relevant ones via embeddings and RAG, generates warm human-like responses, and provides real-time voice calls with VAD+ASR+TTS — all running on **AMD ROCm** compute.

**Live demo:** https://sweet-overall-county-responsible.trycloudflare.com

---

## Innovation Features

### 1. Memory Atlas (Timeline View)
A visual timeline page that groups fictional memories by life category (Childhood, Family, Career, Advice, Faith & Kindness, Humor). Each memory card shows category, emotion, tags, and the full story text.

### 2. Explainable RAG Panel
Every chat response includes a transparent "How This Answer Was Generated" panel showing:
- Your question
- Embedding model used (Qwen3-Embedding-0.6B)
- Vector database (ChromaDB with cosine similarity)
- Top 3 retrieved memories with relevance scores
- Final LLM model used (Qwen2.5-7B-Instruct)
- Retrieval time, generation time, and total time in milliseconds

### 3. Real-Time Voice Call Pipeline
Full live call with VAD detection → SenseVoice ASR → /chat RAG → TTS speech → avatar reaction:
- Voice Activity Detection via `@ricky0123/vad-web` with session tokens and stale-closure prevention
- Backend SenseVoiceSmall ASR for transcription
- AbortController cancellation for every stage (VAD, ASR, chat, TTS)
- Explicit state machine (9 states: idle → requesting_mic → listening → user_speaking → transcribing → sending_to_chat → ai_thinking → ai_speaking → listening loop)
- Barge-in support: user speech interrupts AI speaking immediately
- Session isolation: each call gets a unique session token; results from old calls never affect active calls
- TTS watchdog: 15-second timeout prevents stuck speech from blocking the pipeline

### 4. Consent & Safety Guardrail
A clear ethical notice displayed prominently:
> "Memory Twin AI is a consent-based digital memory simulation. It does not claim to be a real person. It answers only from stored fictional memories. No real personal data is used."

### 5. AMD Compute Proof Page
A dedicated page that fetches `/compute-status` and displays:
- Device name, Torch version, ROCm/CUDA availability
- LLM model, Embedding model, TTS model, ASR model
- Model cache path, ChromaDB path
- **"Copy Proof Text"** button — copies formatted AMD compute proof to clipboard

### 6. Hackathon Demo Mode
Runs 3 preset questions sequentially:
1. *"What advice would you give me?"*
2. *"Tell me about your childhood."*
3. *"What made you proud?"*

Each step shows: AI answer, retrieved memories, AMD compute status, and timing.

### 7. Reliable Memory Saving
Memory detection in chat ("remember that...", "my favorite...") now follows a guaranteed path:
1. Detect memory intent
2. Validate extracted memory (dangerous input rejection via regex patterns)
3. Call POST /memories API
4. Wait for backend persistence confirmation with `memory_id`
5. Incremental ChromaDB upsert (no full rebuild)
6. Display confirmed "Memory saved" with ID
7. On failure: display "Memory was not saved. Retry."

### 8. Retry with Full Context Preservation
Every failed message stores a complete `retry_payload` including:
- Original question text
- Request ID
- Companion selection
- History snapshot
- Temporary context reference

The Retry button calls `retryMessage(messageId)` which resends the original payload — never the cleared input field.

---

## Why This Is Original

"The originality of Memory Twin AI is not training a new foundation model; it is the consent-aware memory architecture, explainable RAG flow, emotional memory interface, real-time voice pipeline, and AMD-powered inference pipeline."

---

## WhatsApp-style Memory Chat

User messages and AI replies are displayed like a modern messenger:
- User messages appear as green bubbles on the right
- AI responses appear as white bubbles on the left with companion avatar
- Each message shows a formatted timestamp (from stored `created_at`)
- Typing indicator with animated dots while backend generates
- "based on memories" badge only when memories were actually retrieved
- Error bubbles include a Retry button
- Imported files validate size (5MB max), character count (50K max), chunk count (200 max)

---

## 3D Live Companion (Three.js)

The app includes a real-time 3D anime-style companion powered by Three.js + React Three Fiber:
- **434 KB optimized GLB** model with full bone rig
- **Choose companion:** Select Male or Female before starting (persists in localStorage)
- **Door opening animation:** Companion enters through an animated door
- **Reactive states:** idle, listening, thinking (with particle effects), speaking (with mouth animation), greeting, emotional reactions
- **Browser TTS** with gender-specific voice selection:
  - Male: pitch 0.92, rate 0.88
  - Female: pitch 1.08, rate 0.94
- **Mute/Replay/Stop controls** in LiveAvatarPanel
- **Mood detection:** Companion reacts based on memory context:
  - Humor → funny expression
  - Career → proud expression
  - Advice → thoughtful expression
  - Faith & Kindness → kind expression
  - Otherwise → calm/warm expression
- **Avatar Action Director:** Qwen3-0.6B refines gesture plans while speech plays

---

## Models

All 9 models downloaded and loadable from ModelScope/HuggingFace:

| Key | Model | Size | Status |
|-----|-------|------|--------|
| llm | Qwen/Qwen2.5-7B-Instruct | ~4 GB | ✅ Flash Attention 2, bfloat16 |
| embedding | Qwen/Qwen3-Embedding-0.6B | ~0.6 GB | ✅ 1024-dim, normalized |
| tts | iic/CosyVoice-300M | ~1.5 GB | ✅ Synthetic companion speech |
| tts2 | iic/CosyVoice2-0.5B | ~2 GB | ✅ Enhanced TTS |
| asr | iic/SenseVoiceSmall | ~0.5 GB | ✅ Voice transcription |
| reranker | Qwen/Qwen3-Reranker-0.6B | ~0.6 GB | ✅ Re-ranking retrieved memories |
| emotion | iic/emotion2vec_plus_large | ~2 GB | ✅ Emotion detection |
| avatar_action | Qwen/Qwen3-0.6B | ~1.6 GB | ✅ Gesture direction |
| avatar_video | AI-ModelScope/MuseTalk | ~3.4 GB | ✅ Lip-sync avatar video |

Models are stored **outside** the repo in `/workspace/memory_twin_models/` (excluded via `.gitignore`).

---

## Dataset Role (Important)

**The dataset is NOT used to train the model.** It serves as the **Memory Vault** — a collection of fictional memories that the system retrieves from via RAG.

| Dataset | Role | Usage |
|---------|------|-------|
| `memories.json` (custom) | **Primary Memory Vault** | Embedded into ChromaDB for RAG retrieval |
| Imported WhatsApp/JSON files | **Temporary Context** | sessionStorage, bounded & validated |

---

## Architecture

```
User text or voice
    ↓
Input validation (sanitize, reject injection)
    ↓
Optional memory-save detection (auto_memory_extractor)
    ↓
VAD detection or typed input
    ↓
SenseVoice ASR (backend) ↔ browser SpeechRecognition fallback
    ↓
Fast route classification (greeting / memory / exact / app-identity)
    ↓
Hybrid retrieval (BM25 + dense embeddings + RRF fusion)
    ↓
ChromaDB cosine search (HNSW, ef_search=100, ef_construction=200)
    ↓
Optional reranker (Qwen3-Reranker-0.6B)
    ↓
Qwen2.5-7B-Instruct response generation
    ↓
Language guard (English-only enforcement)
    ↓
Safe response guard (fallback_answer.py)
    ↓
Avatar mood + animation plan (avatar_director.py)
    ↓
Browser TTS ↔ backend CosyVoice TTS
    ↓
Return safely to listening / idle
```

### Backend Concurrency

```
asyncio event loop
  ├── Semaphore(1) — LLM generation
  ├── Semaphore(1) — Embedding computation
  ├── Semaphore(1) — ASR transcription
  ├── Semaphore(1) — TTS synthesis
  └── ThreadPoolExecutor(4) — blocking LLM calls
```

### Error Handling

Structured error codes returned from every endpoint:
- `CHAT_TIMEOUT` (retryable), `CHAT_CANCELLED`, `BACKEND_UNREACHABLE`
- `ASR_UNAVAILABLE`, `ASR_TIMEOUT`, `ASR_CANCELLED`
- `TTS_UNAVAILABLE`, `TTS_CANCELLED`
- `MEMORY_SAVE_FAILED` (retryable), `MEMORY_VALIDATION_FAILED`
- `MODEL_UNAVAILABLE` (retryable), `RETRIEVAL_FAILED` (retryable)
- `QUEUE_FULL`, `INTERNAL_ERROR` (retryable)

---

## AMD Compute

```text
Torch Version: 2.9.1+gitff65f5b
ROCm Version: ROCm (AMD)
GPU Available: True
Device: AMD Radeon Graphics
LLM Model: Qwen/Qwen2.5-7B-Instruct
Embedding Model: Qwen/Qwen3-Embedding-0.6B
TTS Model: iic/CosyVoice-300M
ASR Model: iic/SenseVoiceSmall
Model Cache: /workspace/memory_twin_models
ChromaDB Path: /workspace/memory_twin_chroma
```

Evidence endpoints:
- `GET /compute-status` — full JSON device report
- `GET /compute` — alias for the same endpoint
- Every `/chat` response includes `compute_status`

---

## Project Structure

```
projects/ai-chat/
├── backend/
│   ├── app.py                          # FastAPI entry (all endpoints)
│   ├── config.py                       # Model IDs, paths, feature toggles
│   ├── core/
│   │   ├── service_container.py        # Singleton DI container
│   │   ├── lru_cache.py                # Thread-safe LRU with TTL
│   │   └── lifespan.py                 # Startup/shutdown lifecycle
│   ├── models/
│   │   ├── model_registry.py           # Path detection for all 9 models
│   │   ├── llm_loader.py               # Qwen2.5-7B-Instruct (flash_attn2, bf16)
│   │   ├── embedding_loader.py         # Qwen3-Embedding-0.6B (SentenceTransformer)
│   │   ├── tts_loader.py               # CosyVoice-300M
│   │   ├── tts_service.py              # CosyVoice2 service
│   │   ├── asr_loader.py               # SenseVoiceSmall (FunASR)
│   │   ├── avatar_video_loader.py      # MuseTalk
│   │   └── emotion_service.py          # emotion2vec + text heuristics
│   ├── services/
│   │   ├── auto_memory_extractor.py    # Inline memory extraction from chat
│   │   ├── avatar_director.py          # Mood → expression/gesture planner
│   │   ├── companion_profile.py        # Male/female companion configs
│   │   ├── conversation_memory.py      # Sliding-window history trimmer
│   │   ├── fallback_answer.py          # Safe fallback answers
│   │   ├── fast_query_router.py        # Deterministic route classification
│   │   ├── language_guard.py           # English-only enforcement
│   │   ├── memory_importer.py          # WhatsApp/JSON → SQLite + Chroma
│   │   ├── reranker_service.py         # Qwen3-Reranker
│   │   ├── streaming_llm_service.py    # SSE streaming LLM
│   │   ├── style_profile_builder.py    # Companion style profiles
│   │   └── voice_router.py             # TTS routing: v2 → v1 → browser
│   ├── rag/
│   │   ├── memory_store.py             # ChromaDB (cosine, HNSW, upsert)
│   │   ├── retriever.py               # Hybrid (dense+BM25+RRF)
│   │   ├── question_classifier.py      # 7-category classifier
│   │   ├── answer_classifier.py        # EXACT/INFERENCE/UNKNOWN
│   │   ├── source_cards.py            # Verbatim source card builder
│   │   ├── temporal_retriever.py       # Date-filtered retrieval
│   │   └── query_transform.py         # HyDE + RRF fusion
│   ├── utils/
│   │   ├── compute_status.py           # AMD/ROCm status reporter
│   │   └── logging_config.py          # JSON/plain logging config
│   ├── tests/
│   │   ├── test_app_concurrency.py     # Error codes, semaphores, lifecycle
│   │   └── test_memory_truth_contract.py # 731-line comprehensive test suite
│   └── scripts/
│       ├── download_selected_models.py
│       ├── download_upgrade_models.py
│       ├── download_avatar_action_model.py
│       └── verify_selected_models.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx                    # Root with 7 routes + companion panel
│   │   ├── context/ChatContext.jsx    # Persistent messages via localStorage
│   │   ├── api/
│   │   │   ├── memoryApi.js           # requestJson helper, SSE streaming, saveMemory
│   │   │   └── asrApi.js              # ASR transcription client
│   │   ├── avatar/
│   │   │   ├── VirtualCompanion.jsx   # Three.js 3D companion
│   │   │   ├── AvatarController.js    # GLB pose controller
│   │   │   ├── LipSyncController.js   # Audio-reactive lip sync
│   │   │   ├── FacialController.js    # Expression blending
│   │   │   └── ProceduralRigController.js # Procedural bone animation
│   │   ├── components/ (18 total)
│   │   │   ├── ChatScreen.jsx         # WhatsApp-style chat with retry, import, memory save
│   │   │   ├── LiveCallScreen.jsx     # VAD → ASR → /chat → TTS state machine
│   │   │   ├── AnimeAvatarStage.jsx   # SVG 2D companion (fallback)
│   │   │   ├── LiveAvatarPanel.jsx    # Right sidebar with companion, controls, engine status
│   │   │   ├── CompanionSelector.jsx  # Male/female selection cards
│   │   │   ├── VoiceSelector.jsx      # Voice dropdown
│   │   │   ├── MemoryVault.jsx        # Memory card browser
│   │   │   ├── MemoryAtlas.jsx        # Timeline grouped by category
│   │   │   ├── AMDProof.jsx           # Compute proof with copy-to-clipboard
│   │   │   ├── AMDComputeStatus.jsx   # Mini compute status panel
│   │   │   ├── HackathonDemo.jsx      # 3-question automated demo
│   │   │   ├── RAGTracePanel.jsx      # Explainable RAG panel
│   │   │   ├── ImportMemory.jsx       # Per-message file import
│   │   │   └── GlowingOrb.jsx         # Decorative animated orb
│   │   └── utils/
│   │       ├── voiceEngine.js         # Browser TTS with op IDs, watchdog, reactive state
│   │       ├── vadRecorder.js          # VAD with state machine, session tokens, audio validation
│   │       ├── liveSpeechRecognition.js # Browser SpeechRecognition fallback
│   │       ├── activeTranscriber.js    # Mutual exclusion: VAD ↔ browser SR
│   │       ├── avatarMood.js          # Mood inference from answer
│   │       ├── avatarActionPlan.js    # Avatar action plan generator
│   │       ├── memoryDetector.js      # Memory save intent detection
│   │       ├── importParser.js        # WhatsApp TXT/JSON parser
│   │       ├── tempImportStore.js     # sessionStorage wrapper
│   │       └── languageGuard.js       # English-only safety net
│   └── styles.css                     # Warm premium UI
├── scripts/
│   └── deploy_cloud.sh                # Production deployment script
├── README.md
├── PROJECT_GUIDE.md
└── .gitignore
```

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+
- AMD GPU with ROCm recommended (CPU fallback available)

### 1. Clone & Install

```bash
git clone https://github.com/madhavabrightly/ai-chat.git
cd projects/ai-chat

# Backend
pip install -r backend/requirements.txt

# Frontend
cd frontend
NODE_ENV=development npm install
```

### 2. Download Models

```bash
# Core models (LLM, embedding, TTS, ASR, avatar action, MuseTalk)
python backend/scripts/download_selected_models.py

# Upgrade models (reranker, emotion, CosyVoice2)
python backend/scripts/download_upgrade_models.py

# Optional: avatar action director
python backend/scripts/download_avatar_action_model.py
```

### 3. Run

```bash
# Terminal 1: Backend
cd /workspace/projects/ai-chat/backend
python -m uvicorn app:app --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd /workspace/projects/ai-chat/frontend
npm run dev -- --host 0.0.0.0 --port 3090
```

Open **http://localhost:3090** in your browser.

### 4. Public Tunnel (for sharing)

```bash
cloudflared tunnel --url http://127.0.0.1:3090 --no-tls-verify
```

---

## Tests

### Frontend (99 tests, 7 files)

```bash
cd /workspace/projects/ai-chat/frontend
NODE_ENV=development npx vitest run
```

| Test File | Tests | Coverage |
|-----------|-------|----------|
| memoryApi.test.js | 15 | requestJson, error handling, cancellation |
| ChatContext.test.jsx | 12 | CRUD, persistence, validation, retry payloads |
| voiceEngine.test.js | 17 | op IDs, callbacks, cancel, subscriptions |
| vadRecorder.test.js | 13 | state machine, session isolation, stale callbacks |
| liveSpeechRecognition.test.js | 19 | support detection, state machine, callbacks |
| activeTranscriber.test.js | 22 | mutual exclusion, pause/resume, subscriptions |
| VirtualCompanion.test.jsx | 1 | 3D avatar rendering |

### Backend

```bash
cd /workspace/projects/ai-chat
python -m pytest backend/tests/test_app_concurrency.py -v
python -m pytest backend/tests/test_memory_truth_contract.py -v
python -m pytest backend/tests/test_avatar_director.py -v
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Liveness probe |
| GET | /compute-status | AMD ROCm device report |
| GET | /compute | Alias for compute-status |
| GET | /memories | List all memories |
| POST | /memories | Save a new memory (validated, atomic write, incremental ChromaDB) |
| POST | /chat | RAG chat (async, semaphore-guarded, timeout 45s) |
| POST | /chat/stream | SSE streaming chat |
| POST | /reload-memory | Rebuild ChromaDB index |
| POST | /memory/import/preview | Upload file → parse → preview |
| GET | /{full_path:path} | SPA fallback (serves frontend) |

---

## Key Architecture Decisions

- **No model training** — pre-trained models used as-is. Innovation is in the RAG architecture, real-time voice pipeline, consent-aware design, and AMD-powered inference.
- **VAD + SenseVoice ASR** over browser SpeechRecognition — VAD (`@ricky0123/vad-web`) detects speech start/end reliably, backend SenseVoiceSmall provides proper ASR.
- **State machine for live call** — explicit 9-state state machine prevents race conditions, stale closures, and resource leaks.
- **Session tokens** — every VAD instance, ASR request, chat request, and TTS operation gets a unique token ensuring old callbacks never affect current state.
- **Incremental ChromaDB** — saves use `upsert()` (idempotent) and bump memory version, no full rebuild.
- **TTS watchdog** — 15-second timeout per utterance chunk prevents stuck speech from blocking the voice pipeline.
- **SVG + Three.js hybrid** — SVG anime companion as instant fallback, Three.js 3D GLB for rich animation when available.

---

## License

MIT — Open Innovation for the AMD Developer Hackathon 2026
