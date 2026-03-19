"""
NeuroChat Configuration
"""
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
VECTOR_DIR = DATA_DIR / "vectors"
DB_PATH = DATA_DIR / "neurochat.db"

# Create directories
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
VECTOR_DIR.mkdir(exist_ok=True)

# Advanced feature directories
MEMORY_STORE_DIR = DATA_DIR / "memory_store"
WATCH_DIR = DATA_DIR / "watch_folder"
NOTES_DIR = DATA_DIR / "notes"
MEMORY_STORE_DIR.mkdir(exist_ok=True)
WATCH_DIR.mkdir(exist_ok=True)
NOTES_DIR.mkdir(exist_ok=True)

# Ollama settings
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# Embedding settings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

# Chunking settings
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# Memory settings
MEMORY_DECAY_RATE = 0.01  # Per day
MEMORY_CONSOLIDATION_THRESHOLD = 20  # Messages before consolidation
MAX_CONTEXT_MEMORIES = 5
MAX_CONTEXT_DOCUMENTS = 3

# Search settings
SEARCH_TOP_K = 10
RERANK_TOP_K = 5
SIMILARITY_THRESHOLD = 0.3

# Server settings
HOST = "0.0.0.0"
PORT = 8000
