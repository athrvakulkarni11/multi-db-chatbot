"""
Advanced Features Router — Knowledge Graph, Sentiment, Topics, Suggestions, Export
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/advanced", tags=["Advanced Features"])

# These will be set during app startup
knowledge_graph_service = None
sentiment_service = None
topic_cluster_service = None
followup_service = None
doc_summary_service = None
export_service = None


# --- Request schemas ---
class TextInput(BaseModel):
    text: str


class SentimentRequest(BaseModel):
    conversation_id: str


class ClusterRequest(BaseModel):
    n_clusters: int = 5


class FollowUpRequest(BaseModel):
    user_message: str
    assistant_response: str
    context: str = ""


class SummarizeRequest(BaseModel):
    text: str
    filename: str = "document"


# --- Knowledge Graph ---
@router.get("/knowledge-graph")
async def get_knowledge_graph():
    """Get the full knowledge graph."""
    if not knowledge_graph_service:
        raise HTTPException(503, "Knowledge graph service not initialized")
    return knowledge_graph_service.get_graph()


@router.post("/knowledge-graph/build")
async def build_knowledge_graph():
    """Build/rebuild knowledge graph from all memories."""
    if not knowledge_graph_service:
        raise HTTPException(503, "Knowledge graph service not initialized")
    knowledge_graph_service.nodes.clear()
    knowledge_graph_service.edges.clear()
    knowledge_graph_service.build_from_memories()
    graph = knowledge_graph_service.get_graph()
    return {
        "status": "built",
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
        "graph": graph
    }


@router.post("/knowledge-graph/extract")
async def extract_from_text(req: TextInput):
    """Extract entities and relationships from text."""
    if not knowledge_graph_service:
        raise HTTPException(503, "Knowledge graph service not initialized")
    knowledge_graph_service.add_from_text(req.text)
    return knowledge_graph_service.get_graph()


# --- Sentiment Analysis ---
@router.post("/sentiment/analyze")
async def analyze_sentiment(req: TextInput):
    """Analyze sentiment of a text."""
    if not sentiment_service:
        raise HTTPException(503, "Sentiment service not initialized")
    return sentiment_service.analyze_sentiment(req.text)


@router.post("/sentiment/conversation")
async def conversation_sentiment(req: SentimentRequest):
    """Get sentiment timeline for a conversation."""
    if not sentiment_service:
        raise HTTPException(503, "Sentiment service not initialized")
    timeline = sentiment_service.get_conversation_sentiment(req.conversation_id)
    
    if not timeline:
        return {"timeline": [], "overall": "neutral", "average_score": 0}
    
    avg_score = sum(t["score"] for t in timeline) / len(timeline)
    overall = "positive" if avg_score > 0.2 else "negative" if avg_score < -0.2 else "neutral"
    
    return {
        "timeline": timeline,
        "overall": overall,
        "average_score": round(avg_score, 3),
        "message_count": len(timeline)
    }


# --- Topic Clustering ---
@router.post("/topics/cluster")
async def cluster_memories(req: ClusterRequest):
    """Cluster all memories by topic."""
    if not topic_cluster_service:
        raise HTTPException(503, "Topic cluster service not initialized")
    
    from models.database import MemoryDB
    memories = MemoryDB.list_all(limit=200)
    
    if not memories:
        return {"clusters": [], "total_memories": 0}
    
    clusters = topic_cluster_service.cluster_memories(memories, req.n_clusters)
    return {
        "clusters": clusters,
        "total_memories": len(memories),
        "num_clusters": len(clusters)
    }


# --- Follow-up Suggestions ---
@router.post("/suggestions/followup")
async def suggest_followups(req: FollowUpRequest):
    """Generate follow-up question suggestions."""
    if not followup_service:
        raise HTTPException(503, "Follow-up service not initialized")
    suggestions = followup_service.suggest_followups(
        req.user_message, req.assistant_response, req.context
    )
    return {"suggestions": suggestions}


# --- Document Summarization ---
@router.post("/summarize")
async def summarize_text(req: SummarizeRequest):
    """Summarize a document or text."""
    if not doc_summary_service:
        raise HTTPException(503, "Summary service not initialized")
    return doc_summary_service.summarize_document(req.text, req.filename)


# --- Conversation Export ---
@router.get("/export/{conversation_id}/markdown")
async def export_markdown(conversation_id: str):
    """Export a conversation as Markdown."""
    from services.advanced_service import ConversationExportService
    content = ConversationExportService.export_markdown(conversation_id)
    if not content:
        raise HTTPException(404, "Conversation not found")
    return PlainTextResponse(content, media_type="text/markdown",
                            headers={"Content-Disposition": f"attachment; filename=conversation_{conversation_id[:8]}.md"})


@router.get("/export/{conversation_id}/json")
async def export_json(conversation_id: str):
    """Export a conversation as JSON."""
    from services.advanced_service import ConversationExportService
    data = ConversationExportService.export_json(conversation_id)
    if not data:
        raise HTTPException(404, "Conversation not found")
    return JSONResponse(data)
