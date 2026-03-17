"""
Memory Router — API endpoints for memory management
"""
from fastapi import APIRouter, HTTPException
from models.schemas import MemoryCreate, MemoryOut, MemorySearchRequest, MemoryUpdate
from services.memory_service import MemoryService

router = APIRouter(prefix="/api/memories", tags=["Memory"])

memory_service: MemoryService = None


def init_router(service: MemoryService):
    global memory_service
    memory_service = service


@router.get("/")
async def list_memories(memory_type: str = None, limit: int = 50):
    """List all memories."""
    if not memory_service:
        raise HTTPException(status_code=500, detail="Memory service not initialized")
    return memory_service.get_all_memories(memory_type=memory_type, limit=limit)


@router.post("/")
async def create_memory(request: MemoryCreate):
    """Manually create a memory."""
    if not memory_service:
        raise HTTPException(status_code=500, detail="Memory service not initialized")
    return memory_service.create_memory(
        content=request.content,
        memory_type=request.memory_type,
        importance=request.importance,
        tags=request.tags
    )


@router.post("/search")
async def search_memories(request: MemorySearchRequest):
    """Search memories semantically."""
    if not memory_service:
        raise HTTPException(status_code=500, detail="Memory service not initialized")
    return memory_service.search_memories(
        query=request.query,
        top_k=request.top_k,
        memory_type=request.memory_type
    )


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a memory."""
    if not memory_service:
        raise HTTPException(status_code=500, detail="Memory service not initialized")
    memory_service.delete_memory(memory_id)
    return {"status": "deleted"}


@router.get("/stats")
async def memory_stats():
    """Get memory statistics."""
    if not memory_service:
        raise HTTPException(status_code=500, detail="Memory service not initialized")
    return memory_service.get_stats()


@router.post("/decay")
async def apply_decay():
    """Manually trigger memory decay."""
    if not memory_service:
        raise HTTPException(status_code=500, detail="Memory service not initialized")
    memory_service.apply_memory_decay()
    return {"status": "decay_applied"}
