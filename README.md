# Memory Twin AI

**AMD Developer Hackathon 2026 — Track 3: Unicorn / Open Innovation**

An AI-powered digital memory twin that stores fictional personal memories, retrieves relevant ones via embeddings and RAG, and generates warm human-like responses using a pre-trained LLM — all running on AMD compute.

## Innovation Features

### 1. Memory Atlas (Timeline View)
A visual timeline page that groups fictional memories by life category (Childhood, Family, Career, Advice, Faith & Kindness, Humor). Each memory card shows category, emotion, tags, and the full story text. The warm card design with category color coding lets you explore the memory timeline like a scrapbook.

### 2. Explainable RAG Panel
Every chat response includes a transparent "How This Answer Was Generated" panel showing:
- Your question
- Embedding model used (Qwen3-Embedding-0.6B)
- Vector database (ChromaDB with cosine similarity)
- Top 3 retrieved memories with relevance scores
- Final LLM model used (Qwen2.5-7B-Instruct)
- Retrieval time, generation time, and total time in milliseconds

Label: *"This explains how Memory Twin AI generated the answer."*

### 3. Consent & Safety Guardrail
A clear ethical notice displayed prominently:
> "Memory Twin AI is a consent-based digital memory simulation. It does not claim to be a real person. It answers only from stored fictional memories. No real personal data is used."

This appears on the Home screen.

### 4. AMD Compute Proof Page
A dedicated page that fetches `/compute-status` and displays:
- Device name, Torch version, ROCm/CUDA availability
- LLM model, Embedding model, Model cache path, ChromaDB path
- Task name, current status
- **"Copy Proof Text"** button — copies a formatted AMD compute proof text block to the clipboard for screenshot/recording

### 5. Hackathon Demo Mode
A dedicated page with a **"Run Hackathon Demo"** button that runs 3 preset questions one by one:
1. *"What advice would you give me?"*
2. *"Tell me about your childhood."*
3. *"What made you proud?"*

Each step shows: AI answer, retrieved memories, AMD compute status, and timing. A completion banner confirms all 3 questions were answered. Designed for demo video recording.

---

## Why This Is Original

"The originality of Memory Twin AI is not training a new foundation model; it is the consent-aware memory architecture, explainable RAG flow, emotional memory interface, and AMD-powered inference pipeline."

---

## WhatsApp-style Memory Chat

User messages and AI replies are displayed like a modern messenger (WhatsApp-inspired):
- User messages appear as green bubbles on the right
- AI responses appear as white bubbles on the left with companion avatar
- Each message shows a timestamp
- Typing indicator with animated dots while backend generates
- "based on memories" badge on AI messages when memory context is used
- Users can save new memories by saying "remember that", "my favorite", "I believe", etc.
- Saved memories show a "💾 Memory saved" confirmation in chat

---

## Adult Anime Companion

The app includes a live 8-bit anime-style companion that reacts to your chat:

- **Choose companion:** Select Male or Female adult companion before starting
- **Companion selection persists** in localStorage across sessions
- **Door opening animation:** Companion appears through an animated door in an 8-bit cozy room
- **Reactive states:** The companion shows listening, thinking (with particle effects), speaking (with mouth animation), and emotional reactions
- **Browser TTS:** Every AI answer is spoken aloud using browser speech synthesis
  - Male companion: pitch 0.9, rate 0.92
  - Female companion: pitch 1.08, rate 0.94
- **Mute/Replay controls:** Toggle voice on/off or replay the last answer
- **Mood detection:** Companion reacts based on memory category:
  - Humor → funny expression
  - Career → proud expression
  - Advice → thoughtful expression
  - Faith & Kindness → kind expression
  - Otherwise → calm/warm expression
- **Always visible:** On desktop, companion panel stays on the right side of chat. On mobile/other pages, it appears as a floating window.
- **Minimize:** Click ➖ to collapse the companion panel when needed

"We intentionally avoid heavy real-time video generation so the companion feels live, fast, and stable during the hackathon demo."

---

## Memory Detection

Users can save memories naturally during chat. The frontend detects intent:
- "remember that..." → saves as Personal Memory
- "my favorite..." → saves as Favorite Thing
- "I believe..." → saves as Personal Belief
- "my dream..." → saves as Life Goal
- "important to me..." → saves as Important Memory

Saved memories appear in the Vault and are available for future RAG retrieval.

---

## How to Test the Companion

1. Open the app → Chat page
2. **Choose companion:** Click "Male Companion" or "Female Companion" card
3. Watch the door open and companion enter the room
4. Companion greets you with voice
5. Type a question → companion shows listening → thinking (particles) → speaking (mouth moves)
6. After answer, companion reacts based on memory mood
7. Use 🔇 Mute to disable voice
8. Use 🔁 Replay to hear the last answer again

---

## How to Test Memory Saving

1. Type "Remember that my favorite color is blue"
2. A "💾 Memory saved: Favorite Thing" message appears
3. Go to Vault page to see the saved memory
4. Ask a question related to that memory

---

## AMD Compute Proof Instructions

1. Go to the **🖥 AMD Proof** page in the sidebar
2. The page automatically fetches `/compute-status` from the backend
3. See device, ROCm/CUDA version, LLM model, embedding model
4. Click **"Copy Proof Text"** to copy a formatted proof block
5. Paste into your submission or capture as a screenshot

---

## Demo Video Recording Flow

1. Start backend → terminal shows AMD Compute Status block (screenshot)
2. Open app → Home screen with consent guardrail
3. Go to **Demo** page → click **"Run Hackathon Demo"**
4. Watch 3 questions run automatically with answers + memories + timing
5. Go to **AMD Proof** page → click **"Copy Proof Text"**
6. Go to **Atlas** → browse memory timeline
7. Go to **Chat** → type a custom question → see RAG trace panel below

---

## Ethical Note

Memory Twin AI is a consent-based digital memory simulation. It does not claim to be a real person. It answers only from stored fictional memories. No real personal data is used. All memories are hand-authored fictional examples demonstrating the architecture.

---

## Track

**Track 3: Unicorn / Open Innovation**

This project is an original AI application. It does not train a foundation model from scratch. Instead, it combines two pre-trained models into a consent-based digital memory simulation system with:

- RAG-powered personal memory vault
- Warm emotional UI (Digital Living Room design)
- Memory Retrieved transparency panel
- AMD Compute Status proof
- Consent-aware ethical design

---

## Problem Statement

People accumulate a lifetime of memories — childhood moments, family traditions, career lessons, words of wisdom, acts of kindness. These memories shape identity, but they are scattered, unstructured, and fade over time.

How might we build a digital companion that can _remember_ like a person — retrieving the right memory at the right moment, and conversing about it with warmth and context?

---

## Solution

Memory Twin AI is a consent-based digital memory simulation that:

1. **Stores** fictional personal memories with emotional metadata in a structured JSON vault
2. **Embeds** each memory as a vector using Qwen3-Embedding-0.6B
3. **Indexes** vectors in ChromaDB for fast cosine-similarity retrieval
4. **Retrieves** the top 3 most relevant memories when a user asks a question
5. **Generates** a warm, natural answer using Qwen2.5-7B-Instruct with the retrieved memories as context
6. **Displays** the answer, retrieved memory cards, and AMD compute status in a premium UI

> **This project uses pre-trained models and does not train a foundation model from scratch. The dataset is used as a consent-based Memory Vault for RAG retrieval. The originality is in the Memory Twin AI system, RAG memory vault, consent-aware design, emotional UI, and AMD-powered AI processing.**

---

## Dataset Role (Important)

**The dataset is NOT used to train the model.**

In this project, the dataset serves as the **Memory Vault** — a collection of fictional memories that the system retrieves from. Here's what each dataset is used for:

| Dataset | Role | Usage |
|---------|------|-------|
| `memories.json` (custom) | **Primary Memory Vault** | Embedded into ChromaDB for RAG retrieval |
| `Synthetic-Persona-Chat` | Style reference | Optional warm speaking style guidance |
| `Nemotron-Personas` | Reference data | Optional persona variety reference |
| `Multi-Round Dialogues` | Reference data | Dialogue flow reference |
| `SoulChatCorpus` | Emotion reference | Emotional response design reference |
| `Multi-Emotion Dialogue` | Emotion reference | Emotional tone reference |
| `RAG-System-Model-Training` | RAG testing | Optional retrieval quality testing |

**None of these datasets are used to fine-tune or train the pre-trained models.**

---

## Why No Pretraining Is Required

Modern pre-trained models are capable of:

- **Qwen3-Embedding-0.6B** — state-of-the-art text embedding. No need to train a custom embedder.
- **Qwen2.5-7B-Instruct** — instruction-tuned chat model. Already knows how to follow prompts, use context, and generate warm responses.

Our innovation is in the **system architecture**:
- How we structure the memory vault
- How we retrieve and rank memories
- How we prompt the LLM to answer from memory only
- How we present retrieved memories transparently to the user
- How we prove AMD compute usage

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                       Memory Twin AI                                │
│                                                                      │
│  ┌──────────────┐   ┌───────────────────┐   ┌──────────────────┐    │
│  │  React +     │   │   FastAPI         │   │   ChromaDB       │    │
│  │  Vite UI     │──▶│   Backend         │──▶│   Vector Store   │    │
│  │              │   │                   │   │                  │    │
│  │  - Chat      │   │  /chat            │   │  memories.json   │    │
│  │  - Orb       │   │  /compute-status  │   │  embedded with   │    │
│  │  - Vault     │   │  /memories        │   │  Qwen3-Embedding │    │
│  │  - Status    │   │  /reload-memory   │   │                  │    │
│  └──────┬───────┘   └──────┬────────────┘   └────────┬─────────┘    │
│         │                  │                          │             │
│         │                  ▼                          │             │
│         │          ┌──────────────┐                   │             │
│         │          │  Qwen2.5-    │                   │             │
│         └──────────│  7B-Instruct │◀──────────────────┘             │
│                    │  (response)  │                                 │
│                    └──────────────┘                                 │
└──────────────────────────────────────────────────────────────────────┘
```

---

## AI Pipeline

```
User Question: "What advice would you give me about life?"
       │
       ▼
┌──────────────────────────────────┐
│  Qwen3-Embedding-0.6B           │
│  Converts question into a       │
│  1024-dim embedding vector      │
└──────────────┬───────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│  ChromaDB                        │
│  Cosine similarity search        │
│  Returns top 3 memories          │
│  + relevance scores              │
└──────────────┬───────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│  Retrieved Memories:             │
│  1. "Advice Under the Stars"     │
│  2. "The Promotion..."           │
│  3. "Learning to Ride a Bike"    │
└──────────────┬───────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│  Qwen2.5-7B-Instruct            │
│  System prompt + memory context │
│  + user question                 │
│  → Generates warm answer         │
└──────────────┬───────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│  Frontend displays:              │
│  - AI answer in card             │
│  - Retrieved memory cards        │
│  - AMD Compute Status panel      │
└──────────────────────────────────┘
```

---

## Models Used

| Role | Model | Source | Size |
|------|-------|--------|------|
| Chat / Response Generation | **Qwen/Qwen2.5-7B-Instruct** | ModelScope / HuggingFace | ~4 GB |
| Embeddings | **Qwen/Qwen3-Embedding-0.6B** | HuggingFace (SentenceTransformer) | ~0.6 GB |

Both models are:
- Pre-trained (no training from scratch)
- Loaded once at server startup (never per request)
- Stored outside the git repo in `/workspace/memory_twin_models/`
- Used as separate variables (`llm_model` / `llm_tokenizer` / `embedder_model`)

---

## Dataset

**6 fictional synthetic memories** across these categories:

| ID | Title | Category | Emotion |
|----|-------|----------|---------|
| mem_001 | Learning to Ride a Bike | Childhood | Joyful |
| mem_002 | Sunday Dinners at Grandma's | Family | Nostalgic |
| mem_003 | The Promotion That Almost Wasn't | Career | Bittersweet |
| mem_004 | Advice Under the Stars | Advice | Warm |
| mem_005 | The Bus Fare Gift | Faith & Kindness | Heartwarming |
| mem_006 | The Talking Parrot Joke | Humor | Amused |

**Ethical note:** All memories are fictional. No real personal data is used. This is a hackathon demo for AMD Developer Hackathon 2026.

---

## AMD Compute Usage Proof

This project demonstrates AMD compute usage through **multiple evidence points** suitable for judging:

### 1. Backend Console Logs (Screenshot)
When the server starts, the terminal prints:
```
==============================================
========== AMD COMPUTE STATUS ==========
Torch Version: 2.4.0
GPU Available: True
Device: AMD GPU (ROCm) — AMD Radeon RX 7900 XTX
LLM Model: Qwen/Qwen2.5-7B-Instruct
Embedding Model: Qwen/Qwen3-Embedding-0.6B
Model Cache: /workspace/memory_twin_models
Task: Memory retrieval + RAG response generation
==============================================
```

### 2. In-App AMD Compute Status Panel (Screenshot)
Click **"AMD Status"** in the top-right of the Chat screen. Shows:
- Provider: AMD Compute
- Device: detected GPU/CPU
- CUDA / ROCm version
- Torch version
- Chat Model: Qwen/Qwen2.5-7B-Instruct
- Embedding Model: Qwen/Qwen3-Embedding-0.6B
- Model Cache path
- Task description
- Status: Active

### 3. API Endpoint
```bash
curl http://localhost:8000/compute-status
```

### 4. Every /chat Response
Every chat response includes compute status in the JSON.

### 5. ROCm Support
On AMD GPUs with ROCm, PyTorch exposes AMD GPUs through `torch.cuda` APIs.
`torch.cuda.is_available()` returns `True` and `torch.cuda.get_device_name(0)` returns the AMD GPU model name.
`torch.version.cuda` returns the ROCm version string.

---

## Project Structure

```
memory_backend/
├── backend/
│   ├── app.py                    # FastAPI entry point
│   ├── config.py                 # Configuration (paths, models, env)
│   ├── .env.example              # Environment template
│   ├── requirements.txt          # Python dependencies
│   ├── data/
│   │   └── memories.json         # Fictional memory dataset
│   ├── models/
│   │   ├── model_registry.py     # All model paths and metadata
│   │   ├── llm_loader.py         # Qwen2.5-7B-Instruct loader
│   │   ├── embedding_loader.py   # Qwen3-Embedding-0.6B loader
│   │   ├── tts_loader.py         # CosyVoice-300M TTS loader
│   │   ├── asr_loader.py         # SenseVoiceSmall ASR loader
│   │   └── avatar_video_loader.py # MuseTalk avatar loader
│   ├── services/
│   │   ├── companion_profile.py  # Male/Female companion profiles
│   │   ├── voice_router.py       # Voice synthesis routing
│   │   ├── avatar_director.py    # Avatar action plan generator
│   │   └── chat_style_engine.py  # Dynamic response instructions
│   ├── rag/
│   │   ├── memory_store.py       # ChromaDB memory store
│   │   └── retriever.py          # Memory retriever
│   ├── utils/
│   │   └── compute_status.py     # AMD compute status reporter
│   └── scripts/
│       ├── download_selected_models.py  # Download only selected models
│       ├── download_datasets.py         # Download reference datasets
│       └── verify_selected_models.py    # Verify downloaded models
├── frontend/
│   ├── package.json              # Node dependencies
│   ├── vite.config.js            # Vite config with API proxy
│   ├── index.html                # HTML entry
│   └── src/
│       ├── main.jsx              # React entry
│       ├── App.jsx               # App root with navigation
│       ├── styles.css            # Warm premium UI styles
│       ├── api/memoryApi.js      # API client
│       ├── utils/
│       │   ├── avatarMood.js     # Mood detection
│       │   ├── memoryDetector.js # Memory save detection
│       │   └── voiceEngine.js    # Browser TTS wrapper
│       └── components/
│           ├── ChatScreen.jsx          # WhatsApp-style chat
│           ├── HomeScreen.jsx          # Landing page
│           ├── MemoryVault.jsx         # Memory card browser
│           ├── MemoryAtlas.jsx         # Timeline view
│           ├── AMDProof.jsx            # Compute proof page
│           ├── HackathonDemo.jsx       # Demo mode
│           ├── LiveAvatarPanel.jsx     # Right-side avatar panel
│           ├── AnimeAvatarStage.jsx    # 8-bit room + character
│           ├── CompanionSelector.jsx   # Male/Female selection
│           ├── RAGTracePanel.jsx       # Explainable RAG
│           └── ... (status, badge, orb)
├── README.md
└── .gitignore
```

---

## Setup Instructions

### Prerequisites

- Python 3.10+
- Node.js 18+
- (Optional) AMD GPU with ROCm for GPU acceleration

### 1. Clone

```bash
git clone <repo-url>
cd memory_backend
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Download Models

Models are ~4.6 GB total and are cached outside the git repo.

```bash
python -m backend.scripts.download_models
```

### 4. Download Reference Datasets (Optional)

```bash
python -m backend.scripts.download_datasets
```

### 5. Run Backend

```bash
cd backend
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

On startup you'll see:
- Model loading logs
- ChromaDB indexing
- **AMD Compute Status block** in the terminal

### 6. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Test with Curl

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What advice would you give me about life?"}'
```

Expected response format:
```json
{
  "answer": "Based on the memories I have...",
  "retrieved_memories": [...],
  "compute_status": {...}
}
```

---

## Demo Video Plan

### Screenshots to Capture (5 screenshots)

1. **Backend terminal** — showing the AMD Compute Status block on startup
2. **Chat screen** — glowing orb, suggested chips, a question asked, the AI answer
3. **Retrieved Memory Cards** — the top-3 memories retrieved for the question
4. **AMD Compute Status panel** — the overlay panel showing all compute details
5. **Memory Vault** — memory cards with a category filter applied

### Video Flow (90 seconds)

| Time | Scene | What to Show |
|------|-------|-------------|
| 0–10s | Terminal | Start backend, show AMD Compute Status block |
| 10–25s | Browser | Open app, show warm UI, glowing orb, pipeline bar |
| 25–50s | Chat | Click "What advice would you give me?" → orb pulses → answer + memory cards appear |
| 50–65s | AMD Status | Click "AMD Status" button → show full compute panel |
| 65–80s | Memory Vault | Click "Memory Vault" → browse memories → apply a category filter |
| 80–90s | Curl | Show terminal curl command and JSON response |

---

---

## Selected Model Download

Only 5 selected models are downloaded — no large video diffusion models:

| Model ID | Key | Purpose | Size |
|----------|-----|---------|------|
| Qwen/Qwen2.5-7B-Instruct | `llm` | Memory-based answer generation | ~4 GB |
| Qwen/Qwen3-Embedding-0.6B | `embedding` | Memory retrieval embeddings | ~0.6 GB |
| iic/CosyVoice-300M | `tts` | Synthetic companion speech | ~1.5 GB |
| iic/SenseVoiceSmall | `asr` | Speech input transcription | ~0.5 GB |
| AI-ModelScope/MuseTalk | `avatar_video` | Optional lip-sync avatar (skipped if disk < 35 GB) | ~3 GB |

Models are stored **outside** the repo in `/workspace/memory_twin_models/`.

### Download Commands

```bash
cd projects/memory_backend
python backend/scripts/download_selected_models.py
```

This will:
- Check available disk space (skip MuseTalk if under 35 GB)
- Download only the listed models
- Skip already-downloaded models
- Save a `models_manifest.json`

### Verify Commands

```bash
# Quick check (embedding model only — fastest)
python backend/scripts/verify_selected_models.py

# Full verification
python backend/scripts/verify_selected_models.py --check-llm
python backend/scripts/verify_selected_models.py --check-tts
python backend/scripts/verify_selected_models.py --check-asr
python backend/scripts/verify_selected_models.py --check-avatar
```

---

## Male/Female Companion Voice Routing

The app provides two adult non-sexual synthetic companion profiles:

**Male Adult Companion:**
- Voice profile: `male_adult_warm`
- Pitch: 0.9, Rate: 0.92
- Speech style: warm, direct, slightly witty, emotionally grounded

**Female Adult Companion:**
- Voice profile: `female_adult_warm`
- Pitch: 1.08, Rate: 0.94
- Speech style: gentle, expressive, thoughtful, lightly playful

Voice routing adjusts by mood:
- **happy:** slightly faster, brighter
- **thoughtful:** slower, softer
- **funny:** playful pace
- **kind:** gentle, warm
- **bored:** slower, low energy (not rude)

If backend TTS (CosyVoice) is unavailable, the frontend falls back to browser `speechSynthesis` with matching pitch/rate settings.

---

## Reactive Anime Avatar Innovation

The avatar action plan summarizes the chat answer into mood, expression, gesture, and movement:

```json
{
  "mood": "calm | happy | thoughtful | funny | kind | proud | bored",
  "expression": "gentle_smile | bright_smile | soft_frown | grin",
  "gesture": "hands_relaxed | hand_chin | hand_wave | hand_heart",
  "movement": "still | gentle_bounce | lean_forward | stand_tall",
  "mouth_style": "normal | excited | slow",
  "short_spoken_summary": "First sentence of answer...",
  "animation_cues": [...]
}
```

Mood rules:
- Humor memory → funny
- Career memory → proud
- Advice memory → thoughtful
- Faith/Kindness memory → kind
- Emotional positive answer → happy
- Default → calm

Lightweight 8-bit CSS animation reacts immediately using these instructions. Optional MuseTalk clip can be generated in the background but chat never freezes waiting for video.

"The innovation is a memory-aware companion that combines RAG, voice routing, avatar direction, and safe real-time anime-style reactions without depending on slow video generation for every turn."

---

## Safety & Ethics

- **Consent-based:** This is a digital memory simulation, not impersonation of a real person
- **No real data:** All memories are fictional synthetic data created for the hackathon
- **Transparency:** The UI clearly labels retrieved memories and the system prompt prevents claims of being real
- **No pretraining:** Models are used as-is with no fine-tuning for the MVP
- **Future scope:** Memory deletion/export can be added; voice cloning would require explicit consent

---

## License

MIT — Open Innovation for the AMD Developer Hackathon 2026
