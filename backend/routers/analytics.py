"""
Analytics Router — API endpoints for analytics dashboard
"""
from fastapi import APIRouter, HTTPException
from models.database import AnalyticsDB, MemoryDB, DocumentDB, ConversationDB, MessageDB
from models.schemas import AnalyticsOverview
from services.search_service import SearchService

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

search_service: SearchService = None


def init_router(service: SearchService):
    global search_service
    search_service = service


@router.get("/overview", response_model=AnalyticsOverview)
async def get_overview():
    """Get a full analytics overview."""
    conversations = ConversationDB.list_all(include_archived=True)
    total_messages = sum(c.get("message_count", 0) for c in conversations)
    memory_stats = MemoryDB.get_stats()
    doc_stats = DocumentDB.get_stats()
    daily_messages = AnalyticsDB.get_daily_counts("chat_message", days=30)

    return AnalyticsOverview(
        total_conversations=len(conversations),
        total_messages=total_messages,
        total_memories=memory_stats["total"],
        total_documents=doc_stats["total"],
        total_document_chunks=doc_stats["total_chunks"],
        memories_by_type=memory_stats["by_type"],
        documents_by_type=doc_stats["by_type"],
        messages_per_day=daily_messages,
        average_memory_importance=memory_stats["average_importance"]
    )


@router.get("/events")
async def get_events(event_type: str = None, days: int = 30, limit: int = 100):
    """Get analytics events."""
    return AnalyticsDB.get_events(event_type=event_type, days=days, limit=limit)


@router.get("/daily")
async def get_daily_counts(event_type: str = None, days: int = 30):
    """Get daily event counts."""
    return AnalyticsDB.get_daily_counts(event_type=event_type, days=days)


@router.get("/search-stats")
async def get_search_stats():
    """Get search index statistics."""
    if not search_service:
        raise HTTPException(status_code=500, detail="Search service not initialized")
    return search_service.get_index_stats()
