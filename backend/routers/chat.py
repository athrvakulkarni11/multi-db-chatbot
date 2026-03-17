"""
Chat Router — API endpoints for chat functionality
"""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from models.schemas import ChatRequest, ChatResponse
from services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Will be set by main.py
chat_service: ChatService = None


def init_router(service: ChatService):
    global chat_service
    chat_service = service


@router.post("/", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Send a message and get a response."""
    if not chat_service:
        raise HTTPException(status_code=500, detail="Chat service not initialized")
    
    result = chat_service.chat(
        message=request.message,
        conversation_id=request.conversation_id
    )
    return result


@router.post("/stream")
async def send_message_stream(request: ChatRequest):
    """Send a message and stream the response."""
    if not chat_service:
        raise HTTPException(status_code=500, detail="Chat service not initialized")

    def event_generator():
        for event in chat_service.chat_stream(
            message=request.message,
            conversation_id=request.conversation_id
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/conversations")
async def list_conversations():
    """List all conversations."""
    if not chat_service:
        raise HTTPException(status_code=500, detail="Chat service not initialized")
    return chat_service.get_conversations()


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a conversation with messages."""
    if not chat_service:
        raise HTTPException(status_code=500, detail="Chat service not initialized")
    conv = chat_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    if not chat_service:
        raise HTTPException(status_code=500, detail="Chat service not initialized")
    chat_service.delete_conversation(conversation_id)
    return {"status": "deleted"}


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(conversation_id: str, title: str):
    """Rename a conversation."""
    if not chat_service:
        raise HTTPException(status_code=500, detail="Chat service not initialized")
    result = chat_service.rename_conversation(conversation_id, title)
    if not result:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result
