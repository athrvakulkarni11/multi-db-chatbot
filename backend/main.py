"""
NeuroChat — Main FastAPI Application
Offline AI Chatbot with Persistent Memory, Document Intelligence,
Tool System, Query Decomposition & File-Based Knowledge Store
"""
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import HOST, PORT, BASE_DIR
from models.database import init_database
from services.llm_service import LLMService
from services.search_service import SearchService
from services.embedding_service import EmbeddingService
from services.memory_service import MemoryService
from services.document_service import DocumentService
from services.chat_service import ChatService
from services.tool_system import ToolRegistry
from services.query_decomposer import QueryDecomposer
from services.watch_folder import WatchFolderService
from routers import chat, memory, documents, analytics, advanced
from routers import system as system_router
from services.advanced_service import (
    KnowledgeGraphService, SentimentService, TopicClusterService,
    FollowUpService, DocumentSummaryService, ConversationExportService
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="NeuroChat",
    description="Offline AI Chatbot with Persistent Memory, Document Intelligence & Tool System",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend static files
FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")


@app.on_event("startup")
async def startup_event():
    """Initialize all services on startup."""
    logger.info("🚀 Starting NeuroChat v2.0...")

    # Initialize database
    init_database()

    # Initialize core services
    logger.info("Loading embedding model...")
    embedding_service = EmbeddingService.get_instance()
    
    search_service = SearchService()
    llm_service = LLMService()
    memory_service = MemoryService(search_service, llm_service)
    document_service = DocumentService(search_service)

    # Initialize tool system
    logger.info("Initializing tool/plugin system...")
    tool_registry = ToolRegistry()

    # Initialize query decomposer
    query_decomposer = QueryDecomposer(llm_service)

    # Initialize chat service with tools + decomposer
    chat_service = ChatService(llm_service, memory_service, document_service)
    chat_service.tool_registry = tool_registry
    chat_service.query_decomposer = query_decomposer

    # Initialize watch folder (auto-indexing)
    logger.info("Starting watch folder auto-indexer...")
    watch_folder_svc = WatchFolderService(document_service)
    watch_folder_svc.start_watching(interval=15)

    # Initialize core routers
    chat.init_router(chat_service)
    memory.init_router(memory_service)
    documents.init_router(document_service)
    analytics.init_router(search_service)

    # Initialize advanced AI services
    logger.info("Initializing advanced AI services...")
    knowledge_graph_svc = KnowledgeGraphService(llm_service)
    sentiment_svc = SentimentService(llm_service)
    topic_cluster_svc = TopicClusterService(embedding_service)
    followup_svc = FollowUpService(llm_service)
    doc_summary_svc = DocumentSummaryService(llm_service)

    # Wire advanced router
    advanced.knowledge_graph_service = knowledge_graph_svc
    advanced.sentiment_service = sentiment_svc
    advanced.topic_cluster_service = topic_cluster_svc
    advanced.followup_service = followup_svc
    advanced.doc_summary_service = doc_summary_svc

    # Wire system router
    system_router.llm_service = llm_service
    system_router.tool_registry = tool_registry
    system_router.watch_folder_service = watch_folder_svc
    system_router.file_memory_store = memory_service.file_store
    system_router.memory_service = memory_service

    # Inject follow-up and sentiment into chat service
    chat_service.followup_service = followup_svc
    chat_service.sentiment_service = sentiment_svc

    # Check Ollama health
    health = llm_service.check_health()
    if health["status"] == "connected":
        logger.info(f"✅ Ollama connected. Model: {health['configured_model']}")
        logger.info(f"   Available models: {', '.join(health.get('models_available', []))}")
    else:
        logger.warning(f"⚠️ Ollama: {health.get('detail', 'Not connected')}")

    logger.info(f"🔧 Tools loaded: {', '.join(tool_registry.tools.keys())}")
    logger.info(f"📁 File memory store: {memory_service.file_store.get_stats()['total']} memories")
    logger.info(f"👁️ Watch folder active: {watch_folder_svc.get_status()['watch_dir']}")
    logger.info("✅ NeuroChat v2.0 is ready!")


# Include all routers
app.include_router(chat.router)
app.include_router(memory.router)
app.include_router(documents.router)
app.include_router(analytics.router)
app.include_router(advanced.router)
app.include_router(system_router.router)


# Health check
@app.get("/api/health")
async def health_check():
    """Check the health of all services."""
    llm = LLMService()
    return {
        "status": "running",
        "llm": llm.check_health(),
        "version": "2.0.0"
    }


# Serve frontend
@app.get("/")
async def serve_frontend():
    """Serve the main frontend HTML."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "NeuroChat API is running. Frontend not found."}


@app.get("/{path:path}")
async def catch_all(path: str):
    """Catch-all route to serve frontend for SPA."""
    file_path = FRONTEND_DIR / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
