# 🧠 NeuroChat — Offline AI Chatbot with Persistent Memory & Document Intelligence

<p align="center">
  <strong>A production-grade, fully offline AI chatbot application with long-term memory, semantic search, and document intelligence.</strong>
</p>

---

## 📋 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [API Documentation](#api-documentation)
- [Screenshots](#screenshots)

---

## ✨ Features

### 🧠 Persistent Long-term Memory
- **Automatic memory extraction** — Learns from every conversation exchange
- **Memory types** — Episodic (events), Semantic (facts), Procedural (how-to)
- **AI-rated importance scoring** — Prioritizes what's worth remembering
- **Memory decay** — Less relevant memories naturally fade over time
- **Memory consolidation** — Auto-summarizes long conversations

### 🔍 Semantic Search Engine
- **Embedding-based retrieval** — Uses `all-MiniLM-L6-v2` sentence-transformers
- **Hybrid search** — Combines dense (FAISS) + sparse (BM25) retrieval
- **Multi-index architecture** — Separate indices for memories and documents
- **Weighted score fusion** — Combines semantic and keyword relevance

### 📄 Document Intelligence
- **Multi-format support** — PDF, DOCX, TXT, Markdown, CSV
- **Smart chunking** — Paragraph-aware text splitting with overlap
- **Automatic indexing** — Documents become searchable immediately
- **Citation tracking** — Responses reference source documents
- **Keyword extraction** — Auto-generated document keywords

### 💬 Advanced Chat Experience
- **Streaming responses** — Real-time token-by-token response
- **Context-aware** — Retrieves relevant memories and documents
- **Multi-conversation** — Create, switch, and manage conversations
- **Context panel** — See exactly what context was used

### 📊 Analytics Dashboard
- **Usage statistics** — Conversations, messages, memories, documents
- **Activity charts** — Messages over time visualization
- **Memory distribution** — Donut chart showing memory types
- **Search index stats** — Vector count and index health

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────────────────────────┐
│  Frontend    │────▶│  FastAPI Backend                  │
│  (HTML/JS)   │     │                                  │
└─────────────┘     │  ┌────────────┐  ┌────────────┐  │
                    │  │ Chat       │  │ Memory     │  │
                    │  │ Service    │  │ Service    │  │
                    │  └───┬───┬────┘  └────┬───────┘  │
                    │      │   │            │           │
                    │  ┌───▼───▼────┐  ┌────▼───────┐  │
                    │  │ LLM        │  │ Search     │  │
                    │  │ (Ollama)   │  │ Service    │  │
                    │  └────────────┘  └────┬───────┘  │
                    │                       │           │
                    │  ┌───────────────┐ ┌──▼────────┐  │
                    │  │ SQLite DB     │ │ FAISS     │  │
                    │  │ (Structured)  │ │ (Vectors) │  │
                    │  └───────────────┘ └───────────┘  │
                    └──────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Backend | Python 3.10+, FastAPI, Uvicorn |
| LLM | Ollama (llama3.2 / mistral / any model) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector Database | FAISS (Facebook AI Similarity Search) |
| Keyword Search | BM25 (rank-bm25) |
| Database | SQLite with WAL mode |
| Doc Parsing | PyPDF2, python-docx, markdown, BeautifulSoup |

---

## 🚀 Getting Started

### Prerequisites

1. **Python 3.10+** — [Download](https://python.org)
2. **Ollama** — [Download](https://ollama.com)

### Installation

```bash
# 1. Clone or navigate to project
cd final-year-project

# 2. Install Ollama and pull a model
ollama pull llama3.2

# 3. Set up Python environment
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the application
python main.py
```

### Quick Start (Windows)

Simply double-click `run.bat` — it handles everything automatically!

### Access

Open your browser and go to: **http://localhost:8000**

---

## 📁 Project Structure

```
final-year-project/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Configuration
│   ├── models/
│   │   ├── database.py          # SQLite models & CRUD
│   │   └── schemas.py           # Pydantic schemas
│   ├── services/
│   │   ├── llm_service.py       # Ollama integration
│   │   ├── embedding_service.py # Sentence-transformers
│   │   ├── memory_service.py    # Memory management
│   │   ├── search_service.py    # FAISS + BM25 hybrid search
│   │   ├── document_service.py  # Document processing
│   │   └── chat_service.py      # Chat orchestration
│   ├── routers/
│   │   ├── chat.py              # Chat endpoints
│   │   ├── memory.py            # Memory endpoints
│   │   ├── documents.py         # Document endpoints
│   │   └── analytics.py         # Analytics endpoints
│   ├── utils/
│   │   ├── chunker.py           # Text chunking
│   │   └── text_processor.py    # Text utilities
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── css/                     # Stylesheets
│   └── js/                      # Client-side logic
├── data/                        # Auto-created
│   ├── neurochat.db
│   ├── vectors/
│   └── uploads/
├── run.bat                      # Windows launcher
└── README.md
```

---

## 📚 API Documentation

Once running, visit **http://localhost:8000/docs** for interactive Swagger documentation.

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/` | Send a message |
| POST | `/api/chat/stream` | Stream a message |
| GET | `/api/chat/conversations` | List conversations |
| GET | `/api/memories/` | List memories |
| POST | `/api/memories/search` | Semantic memory search |
| POST | `/api/documents/upload` | Upload a document |
| POST | `/api/documents/search` | Search documents |
| GET | `/api/analytics/overview` | Get analytics |
| GET | `/api/health` | Health check |

---

## 🎓 Academic Relevance

This project demonstrates mastery of:

1. **Natural Language Processing** — LLM integration, embeddings, semantic search
2. **Information Retrieval** — Hybrid search (dense + sparse), re-ranking
3. **Database Systems** — SQLite CRUD, FAISS vector indexing
4. **Software Engineering** — Modular architecture, API design, full-stack development
5. **Machine Learning** — Sentence-transformers, memory importance scoring
6. **Data Structures** — Vector indices, BM25 inverted indices
7. **Web Development** — Modern UI/UX, real-time streaming, responsive design

---

## 📄 License

This project is created as a final year academic project.
