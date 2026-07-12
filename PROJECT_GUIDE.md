# Memory Twin AI — Complete Project Guide

## Overview
Memory Twin AI is a consent-based digital memory simulation with RAG, 3D companion, live voice call, memory persistence, explainable RAG, and AMD compute proof — built for **AMD Developer Hackathon 2026 (Track 3: Unicorn/Open Innovation)**.

**Live URL:** https://sweet-overall-county-responsible.trycloudflare.com

---

## How to Start the App

### 1. Start Backend
```bash
cd /workspace/projects/ai-chat/backend
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```
Models load on first startup. Wait for:
```
INFO:app:Vector store ready — 18 memories indexed.
========== AMD COMPUTE STATUS ==========
```
Backend runs at `http://localhost:8000`.

### 2. Start Frontend
```bash
cd /workspace/projects/ai-chat/frontend
npm run dev -- --host 0.0.0.0 --port 3090
```
Frontend runs at `http://localhost:3090`. API calls proxy to backend.

### 3. Public Tunnel (for sharing)
```bash
cloudflared tunnel --url http://127.0.0.1:3090 --no-tls-verify
```

---

## All 9 Models (Downloaded & Loadable)

| Key | Model | Path | Size | Status |
|-----|-------|------|------|--------|
| llm | Qwen/Qwen2.5-7B-Instruct | `qwen_llm` | ~4 GB | ✅ Flash Attention 2, bfloat16 |
| embedding | Qwen/Qwen3-Embedding-0.6B | `qwen_embedding` | ~0.6 GB | ✅ 1024-dim, normalized |
| tts | iic/CosyVoice-300M | `cosyvoice_tts` | ~1.5 GB | ✅ |
| tts2 | iic/CosyVoice2-0.5B | `cosyvoice2_tts` | ~2 GB | ✅ |
| asr | iic/SenseVoiceSmall | `sensevoice_asr` | ~0.5 GB | ✅ |
| reranker | Qwen/Qwen3-Reranker-0.6B | `qwen_reranker` | ~0.6 GB | ✅ |
| emotion | iic/emotion2vec_plus_large | `emotion2vec` | ~2 GB | ✅ |
| avatar_action | Qwen/Qwen3-0.6B | `qwen3_avatar_action` | ~1.6 GB | ✅ |
| avatar_video | AI-ModelScope/MuseTalk | `musetalk_avatar` | ~3.4 GB | ✅ |

Model root: `/workspace/memory_twin_models/`
Runtime root: `/workspace/memory_twin_runtime/`
ChromaDB: `/workspace/memory_twin_chroma/`

### Download Commands
```bash
cd /workspace/projects/ai-chat
python backend/scripts/download_selected_models.py
python backend/scripts/download_upgrade_models.py
python backend/scripts/download_avatar_action_model.py
```

---

## AMD Compute Evidence

```text
Torch: 2.9.1+gitff65f5b
ROCm: ROCm (AMD)
GPU: AMD Radeon Graphics
cuda_available: True (AMD GPU via ROCm)
```

Evidence endpoints:
- `GET /compute-status` — full JSON device report
- `GET /compute` — alias
- Every `/chat` response includes `compute_status`

---

## Backend Architecture

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Backend status |
| GET | /compute-status | AMD ROCm device report |
| GET | /compute | Alias |
| GET | /memories | List memories |
| POST | /memories | Save memory (validated, atomic write, incremental ChromaDB) |
| POST | /chat | RAG chat (async, semaphore-guarded, 45s timeout) |
| POST | /chat/stream | SSE streaming chat |
| POST | /reload-memory | Rebuild ChromaDB |
| POST | /memory/import/preview | Upload file → parse |
| POST | /asr/transcribe | ASR transcription |
| POST | /voice/speak | TTS synthesis |
| POST | /avatar/action | Avatar action plan |

### Concurrency
- `asyncio.Semaphore(1)` for LLM, Embedding, ASR, TTS
- `ThreadPoolExecutor(max_workers=4)` for blocking LLM calls
- `asyncio.wait_for()` with 45s timeout per generation

### Error Codes
- `CHAT_TIMEOUT` (retryable), `CHAT_CANCELLED`, `CHAT_GENERATION_FAILED`
- `BACKEND_UNREACHABLE`, `MODEL_NOT_LOADED`, `INVALID_REQUEST`
- `ASR_UNAVAILABLE/TIMEOUT/CANCELLED`, `TTS_UNAVAILABLE/CANCELLED`
- `MEMORY_SAVE_FAILED` (retryable), `MEMORY_VALIDATION_FAILED`
- `MODEL_UNAVAILABLE` (retryable), `RETRIEVAL_FAILED` (retryable)
- `QUEUE_FULL`, `INTERNAL_ERROR` (retryable)

### Request Lifecycle
Every request is tracked via `register_request()` / `complete_request()` / `cancel_request()` in a thread-safe dict.

---

## Frontend Architecture

### Routes (sidebar navigation)
| Route | Component | Features |
|-------|-----------|----------|
| Home | HomeScreen | Landing + consent guardrail + health check |
| Chat | ChatScreen | WhatsApp chat, memory save, retry, RAG trace |
| Live Call | LiveCallScreen | VAD → ASR → /chat → TTS → avatar |
| Vault | MemoryVault | Memory browser with category filters |
| Atlas | MemoryAtlas | Timeline grouped by category |
| AMD Proof | AMDProof | Device report + copy proof |
| Demo | HackathonDemo | 3 preset questions auto-run |

### Live Call State Machine (9 states)
```
idle → requesting_mic → listening → user_speaking → transcribing
    → sending_to_chat → ai_speaking → listening (loop)
    → ended / error (terminal)
    → recovering → listening (on recoverable error)
```

### Session Isolation
Every call generates a unique session token. All callbacks (VAD, ASR, chat, TTS, restart timers) check the token against `callSessionRef.current.token`. If mismatched, the callback is silently dropped.

### Retry Behavior
Every failed message stores a `retry_payload` with:
- Original question, companion type, history snapshot, temp context
- `retryMessage(messageId)` resends this payload — never the cleared input field

### Memory Save Flow
1. Frontend detects memory intent via keyword matching
2. Calls `saveMemory()` → POST /memories
3. Backend validates input (rejects dangerous patterns), saves to JSON atomically, upserts to ChromaDB
4. Returns `{ok: true, memory_id, indexed: true}`
5. Frontend shows "Memory saved: title (manual_0001)" only on success

### TTS Pipeline
- Each utterance gets a unique operation ID
- Separate callbacks: `onStart`, `onEnd`, `onCancel`, `onError`
- 15-second watchdog per chunk prevents stuck speech
- Chunking on sentence boundaries (200 char max per chunk)
- Reactive state via `subscribeSpeaking()` — `LiveAvatarPanel` and `LiveCallScreen` re-render on state change

### Import File Validation
- Max file size: 5 MB
- Max character count: 50,000
- Max chunk count: 200
- Parser errors caught and displayed to user

---

## Tests

### Frontend (99 tests, 7 files, all passing)
```bash
cd /workspace/projects/ai-chat/frontend
NODE_ENV=development npx vitest run
```

| File | Tests | What it covers |
|------|-------|----------------|
| memoryApi.test.js | 15 | requestJson success, HTTP_ERROR, PARSE_ERROR, NETWORK_ERROR, CANCELLED, TIMEOUT |
| ChatContext.test.jsx | 12 | add/update/remove, localStorage persistence, validation, retry payloads, unknown field stripping |
| voiceEngine.test.js | 17 | op IDs, onEnd/onCancel/onError separation, cancellations, subscriptions, gender voice selection |
| vadRecorder.test.js | 13 | state machine, session isolation, stale callback prevention, pause/resume |
| liveSpeechRecognition.test.js | 19 | feature detection, state machine, callbacks, silence timer, stale callback prevention |
| activeTranscriber.test.js | 22 | mutual exclusion (VAD ↔ SR), pause/resume delegation, mode subscriptions |
| VirtualCompanion.test.jsx | 1 | 3D avatar rendering |

### Backend
```bash
cd /workspace/projects/ai-chat
python -m pytest backend/tests/ -q
```

| File | Tests | What it covers |
|------|-------|----------------|
| test_app_concurrency.py | 17 | ErrorCode, make_error, semaphores, request lifecycle, cancellation, health/compute/memories endpoints |
| test_memory_truth_contract.py | ~50 | WhatsApp parser, JSON parser, 7-category question classifier, answer classifier (EXACT/INFERENCE/UNKNOWN), source cards, date filter leakage, English-only enforcement |
| test_avatar_director.py | 3 | Mood → expression/gesture/movement planning |

---

## Project Structure (complete)

```
/workspace/projects/ai-chat/
├── backend/
│   ├── app.py                   # FastAPI entry — all endpoints
│   ├── config.py                # Model IDs, paths, feature toggles
│   ├── core/
│   │   ├── service_container.py # Singleton DI container
│   │   ├── lru_cache.py         # Thread-safe LRU with TTL
│   │   └── lifespan.py          # Startup/shutdown
│   ├── models/
│   │   ├── model_registry.py    # Path detection for 9 models
│   │   ├── llm_loader.py        # Qwen2.5-7B-Instruct
│   │   ├── embedding_loader.py  # Qwen3-Embedding-0.6B
│   │   ├── tts_loader.py        # CosyVoice-300M
│   │   ├── tts_service.py       # CosyVoice2
│   │   ├── asr_loader.py        # SenseVoiceSmall
│   │   ├── avatar_video_loader.py # MuseTalk
│   │   └── emotion_service.py   # emotion2vec
│   ├── services/
│   │   ├── auto_memory_extractor.py  # Inline memory extraction
│   │   ├── avatar_director.py        # Mood → expression planner
│   │   ├── companion_profile.py      # Male/female profiles
│   │   ├── conversation_memory.py    # Sliding-window trimmer
│   │   ├── fallback_answer.py        # Safe fallback answers
│   │   ├── fast_query_router.py      # Route classification
│   │   ├── language_guard.py         # English-only enforcement
│   │   ├── memory_importer.py        # File → SQLite + Chroma
│   │   ├── reranker_service.py       # Qwen3-Reranker
│   │   ├── streaming_llm_service.py  # SSE streaming
│   │   ├── style_profile_builder.py  # Style profiles
│   │   └── voice_router.py           # TTS routing
│   ├── rag/
│   │   ├── memory_store.py           # ChromaDB
│   │   ├── retriever.py             # Hybrid search
│   │   ├── question_classifier.py    # 7-category
│   │   ├── answer_classifier.py      # Truth levels
│   │   ├── source_cards.py          # Source cards
│   │   ├── temporal_retriever.py     # Date-filtered
│   │   └── query_transform.py       # HyDE + RRF
│   ├── utils/
│   │   ├── compute_status.py        # AMD/ROCm reporter
│   │   └── logging_config.py       # JSON logging
│   ├── tests/
│   │   ├── test_app_concurrency.py  # 17 tests
│   │   ├── test_memory_truth_contract.py  # ~50 tests
│   │   └── test_avatar_director.py  # 3 tests
│   ├── data/
│   │   └── memories.json           # 18 fictional memories
│   └── scripts/
│       ├── download_selected_models.py
│       ├── download_upgrade_models.py
│       └── download_avatar_action_model.py
├── frontend/
│   ├── src/
│   │   ├── main.jsx               # React entry
│   │   ├── App.jsx                # Root with 7 routes
│   │   ├── styles.css             # Premium warm UI
│   │   ├── context/ChatContext.jsx # localStorage messages
│   │   ├── api/
│   │   │   ├── memoryApi.js       # requestJson, SSE, saveMemory
│   │   │   └── asrApi.js          # ASR transcription
│   │   ├── avatar/
│   │   │   ├── VirtualCompanion.jsx # Three.js 3D companion
│   │   │   ├── AvatarController.js
│   │   │   ├── LipSyncController.js
│   │   │   ├── FacialController.js
│   │   │   └── ProceduralRigController.js
│   │   ├── components/
│   │   │   ├── ChatScreen.jsx        # Chat with retry, import, memory save
│   │   │   ├── LiveCallScreen.jsx    # VAD → ASR → /chat → TTS
│   │   │   ├── AnimeAvatarStage.jsx  # SVG companion (2D fallback)
│   │   │   ├── LiveAvatarPanel.jsx   # Right sidebar
│   │   │   ├── CompanionSelector.jsx # Male/female picker
│   │   │   ├── VoiceSelector.jsx     # Voice dropdown
│   │   │   ├── MemoryVault.jsx       # Memory browser
│   │   │   ├── MemoryAtlas.jsx       # Timeline
│   │   │   ├── AMDProof.jsx          # Compute proof
│   │   │   ├── AMDComputeStatus.jsx  # Mini status
│   │   │   ├── HackathonDemo.jsx     # Demo mode
│   │   │   ├── RAGTracePanel.jsx     # Explainable RAG
│   │   │   ├── ImportMemory.jsx      # File import
│   │   │   └── GlowingOrb.jsx        # Decorative orb
│   │   └── utils/
│   │       ├── voiceEngine.js         # TTS with op IDs + watchdog
│   │       ├── vadRecorder.js          # VAD state machine
│   │       ├── liveSpeechRecognition.js # Browser SR fallback
│   │       ├── activeTranscriber.js    # Mode coordinator
│   │       ├── avatarMood.js          # Mood inference
│   │       ├── avatarActionPlan.js    # Action plan
│   │       ├── memoryDetector.js      # Intent detection
│   │       ├── importParser.js        # WhatsApp parser
│   │       ├── tempImportStore.js     # sessionStorage
│   │       └── languageGuard.js       # English safety net
│   └── public/
│       ├── vad-assets/               # VAD ONNX models
│       └── models/
│           └── lacrimosa-live.glb    # 3D companion model
├── scripts/
│   └── deploy_cloud.sh              # Deployment script
├── README.md
├── PROJECT_GUIDE.md
└── .gitignore
```

---

## Git Workflow
```bash
cd /workspace/projects/ai-chat
git status
git add -A
git commit -m "message"

Co-authored-by: CommandCodeBot <noreply@commandcode.ai"
EOF
git push origin main
```

Remote: `https://github.com/madhavabrightly/ai-chat.git`
