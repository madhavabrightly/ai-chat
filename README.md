# Memory Twin AI

**AMD Developer Hackathon 2026 — Track 3: Unicorn / Open Innovation**

An AI-powered digital memory twin application. Stores fictional personal memories, retrieves relevant ones using embeddings and RAG (Retrieval-Augmented Generation), and generates warm human-like responses using pre-trained LLMs on AMD compute.

---

## Quick Links

- **GitHub Repo:** https://github.com/madhavabrightly/ai-chat
- **Backend:** FastAPI Python on port 8000
- **Frontend:** React + Vite on port 5173

---

## Project Structure

```
ai-chat/
├── backend/
│   ├── app.py                    # FastAPI server (all endpoints)
│   ├── config.py                 # Paths, model names, env settings
│   ├── requirements.txt          # Python dependencies
│   ├── .env.example              # Environment template
│   ├── data/
│   │   └── memories.json         # 6 fictional demo memories
│   ├── models/
│   │   ├── llm_loader.py         # Qwen2.5-7B-Instruct loader
│   │   └── embedding_loader.py   # Qwen3-Embedding-0.6B loader
│   ├── rag/
│   │   ├── memory_store.py       # ChromaDB vector store
│   │   └── retriever.py          # RAG memory retriever
│   ├── utils/
│   │   └── compute_status.py     # AMD compute status reporter
│   └── scripts/
│       ├── download_models.py    # Download both AI models
│       ├── download_datasets.py  # Download reference datasets
│       └── verify_models.py      # Verify model integrity
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx               # Main app with navigation
│       ├── main.jsx              # React entry
│       ├── styles.css            # Premium warm UI styling
│       └── api/
│           └── memoryApi.js      # API client
├── datasets/                     # Downloaded reference datasets (gitignored)
├── README.md
└── .gitignore
```

---

## Problem Statement

People accumulate a lifetime of memories — childhood moments, family traditions, career lessons, words of wisdom, acts of kindness. These memories shape identity, but they are scattered, unstructured, and fade over time.

Memory Twin AI solves this by building a digital companion that can *remember* like a person — retrieving the right memory at the right moment and conversing about it with warmth and context.

---

## Solution

1. **Stores** fictional personal memories with emotional metadata in a structured JSON vault
2. **Embeds** each memory as a vector using Qwen3-Embedding-0.6B
3. **Indexes** vectors in ChromaDB for fast cosine-similarity retrieval
4. **Retrieves** the top 3 most relevant memories when a user asks a question
5. **Generates** a warm, natural answer using Qwen2.5-7B-Instruct with retrieved memories as context
6. **Displays** the answer, retrieved memory cards, and AMD compute status in a premium UI

> **This project uses pre-trained models and does not train a foundation model from scratch. The dataset is used as a consent-based Memory Vault for RAG retrieval. The originality is in the Memory Twin AI system, RAG memory vault, consent-aware design, emotional UI, and AMD-powered AI processing.**

---

## AI Pipeline

```
User Question
    │
    ▼
Qwen3-Embedding-0.6B ────→ 1024-dim embedding vector
    │
    ▼
ChromaDB ────→ Cosine similarity → top 3 memories
    │
    ▼
Qwen2.5-7B-Instruct ────→ Warm answer + memory context
    │
    ▼
Frontend: answer card + retrieved memory cards + AMD compute status
```

---

## Models Used

| Role | Model | Source | Size |
|------|-------|--------|------|
| Chat / Response Generation | **Qwen/Qwen2.5-7B-Instruct** | [ModelScope](https://www.modelscope.cn/models/Qwen/Qwen2.5-7B-Instruct) / [HuggingFace](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) | ~15 GB (4 shards) |
| Embeddings | **Qwen/Qwen3-Embedding-0.6B** | [HuggingFace](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | ~1.2 GB |

Both models are:
- **Pre-trained only** — no training from scratch, no fine-tuning required
- Loaded **once at server startup** (never per request)
- Stored outside the git repo at `/workspace/memory_twin_models/`
- Used as **separate variables** (`llm_model`, `llm_tokenizer`, `embedder_model`)

---

## Setup Instructions

### Prerequisites

- Python 3.10+
- Node.js 18+
- (Optional) AMD GPU with ROCm 6+ for GPU acceleration
- 20 GB free disk space for model weights + datasets

### 1. Clone

```bash
git clone https://github.com/madhavabrightly/ai-chat.git
cd ai-chat
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Download AI Models (~4.6 GB total)

Models are cached outside the git repo at the path specified in `.env` (default: `/workspace/memory_twin_models/`).

```bash
python -m backend.scripts.download_models
```

This downloads:
- **Qwen/Qwen2.5-7B-Instruct** (~15 GB safetensors across 4 shards) — the chat/response generation model
- **Qwen/Qwen3-Embedding-0.6B** (~1.2 GB) — the embedding model for RAG

**Manual download alternatives:**

For LLM (Qwen2.5-7B-Instruct):
```bash
# Via modelscope
modelscope download --model Qwen/Qwen2.5-7B-Instruct --local_dir /workspace/memory_twin_models/Qwen_Qwen2.5-7B-Instruct

# Via huggingface-cli (requires huggingface_hub installed)
huggingface-cli download Qwen/Qwen2.5-7B-Instruct --local-dir /workspace/memory_twin_models/Qwen_Qwen2.5-7B-Instruct

# Via git LFS
git lfs install
git clone https://huggingface.co/Qwen/Qwen2.5-7B-Instruct /workspace/memory_twin_models/Qwen_Qwen2.5-7B-Instruct
```

For Embedding model (Qwen3-Embedding-0.6B):
```bash
# Via sentence-transformers (Python)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('Qwen/Qwen3-Embedding-0.6B', cache_folder='/workspace/memory_twin_models/Qwen_Qwen3-Embedding-0.6B')"

# Via huggingface-cli
huggingface-cli download Qwen/Qwen3-Embedding-0.6B --local-dir /workspace/memory_twin_models/Qwen_Qwen3-Embedding-0.6B
```

### 4. Download Reference Datasets (Optional, ~6 GB total)

These datasets are **not used for training**. They serve as:
- Style reference for warm speaking patterns
- Emotional response design reference
- RAG retrieval quality testing

```bash
python -m backend.scripts.download_datasets
```

**Or download individually from ModelScope:**

| Dataset | Size | Command |
|---------|------|---------|
| **Synthetic-Persona-Chat** | 38 MB | `modelscope download --dataset google/Synthetic-Persona-Chat` |
| **Nemotron-Personas** | 2.69 GB | `modelscope download --dataset nv-community/Nemotron-Personas` |
| **Multi-Round Dialogues** | 321 KB | `modelscope download --dataset DatatangBeijing/830276groups-Multi_RoundInterpersonalDialoguesTextData` |
| **SoulChatCorpus** | 900 MB | `git clone https://www.modelscope.cn/datasets/YIRONGCHEN/SoulChatCorpus.git` |
| **Multi-Emotion Dialogue** | small | `modelscope download --dataset zhangzhihao/Simplified_Chinese_Multi-Emotion_Dialogue_Dataset` |
| **RAG-System-Model-Training** | 2.31 GB | `modelscope download --dataset TaitaiPhu/RAG-System-Model-Training` |

All datasets source from: **https://www.modelscope.cn**

### 5. Run Backend

```bash
cd ai-chat/backend
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

On startup you'll see:
- Model loading logs
- ChromaDB indexing of 6 memories
- **AMD Compute Status block** in the terminal

The backend serves both the API and the built frontend UI at `http://localhost:8000`.

### 6. Frontend Development (Optional)

For hot-reload UI development:

```bash
cd ai-chat/frontend
npm install
npm run dev
```

Opens at `http://localhost:5173` with API proxy to port 8000.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/compute-status` | AMD compute / device details |
| GET | `/memories` | List all memories |
| POST | `/chat` | RAG chat: question → answer + retrieved memories |
| POST | `/reload-memory` | Rebuild ChromaDB from memories.json |

### Test with curl

```bash
# Health
curl http://localhost:8000/health

# Compute status (AMD proof)
curl http://localhost:8000/compute-status

# Chat (RAG pipeline)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What advice would you give me about life?"}'
```

### Expected /chat response

```json
{
  "answer": "Based on the memories I have, I would say...",
  "retrieved_memories": [
    {
      "memory_id": "mem_004",
      "title": "Advice Under the Stars",
      "category": "Advice",
      "relevance_score": 0.38,
      ...
    }
  ],
  "compute_status": {
    "device": "AMD Radeon Graphics",
    "llm_model": "Qwen/Qwen2.5-7B-Instruct",
    "embedding_model": "Qwen/Qwen3-Embedding-0.6B",
    ...
  }
}
```

---

## AMD Compute Usage Proof

This project runs on AMD compute and proves it through:

### 1. Backend Console Logs
Every startup prints:
```
==============================================
========== AMD COMPUTE STATUS ==========
Torch Version: 2.9.1+gitff65f5b
GPU Available: True
Device: AMD Radeon Graphics
LLM Model: Qwen/Qwen2.5-7B-Instruct
Embedding Model: Qwen/Qwen3-Embedding-0.6B
Model Cache: /workspace/memory_twin_models
Task: Memory retrieval + RAG response generation
==============================================
```

### 2. API Endpoint
```bash
curl http://localhost:8000/compute-status
```

### 3. In-App Panel
Click "AMD Compute" panel in the UI sidebar — shows device, models, cache paths, and task info.

### 4. Every Chat Response
Every `/chat` response includes a `compute_status` object with live device data.

---

## Dataset

**6 fictional synthetic memories** (in `backend/data/memories.json`):

| ID | Title | Category | Emotion |
|----|-------|----------|---------|
| mem_001 | Learning to Ride a Bike | Childhood | Joyful |
| mem_002 | Sunday Dinners at Grandma's | Family | Nostalgic |
| mem_003 | The Promotion That Almost Wasn't | Career | Bittersweet |
| mem_004 | Advice Under the Stars | Advice | Warm |
| mem_005 | The Bus Fare Gift | Faith & Kindness | Heartwarming |
| mem_006 | The Talking Parrot Joke | Humor | Amused |

**Ethical note:** All memories are fictional. No real personal data is used.

---

## Safety & Ethics

- **Consent-based:** This is a digital memory simulation, not impersonation of a real person
- **No real data:** All memories are fictional synthetic data
- **Transparency:** The UI clearly labels retrieved memories; the system prompt prevents claims of being real
- **No pretraining:** Models are used as-is with no fine-tuning for the MVP
- **Voice cloning disclaimer:** Any future voice features would require explicit consent

---

## License

MIT — Open Innovation for the AMD Developer Hackathon 2026
