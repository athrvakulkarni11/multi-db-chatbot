"""
System Router — Model management, tool info, watch folder, file memory
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/system", tags=["System"])

# Injected at startup
llm_service = None
tool_registry = None
watch_folder_service = None
file_memory_store = None
memory_service = None


class ModelSwitchRequest(BaseModel):
    model_name: str


# --- Model Management ---
@router.get("/models")
async def list_models():
    """List available Ollama models."""
    if not llm_service:
        raise HTTPException(503, "LLM service not initialized")
    models = llm_service.get_available_models()
    return {
        "current_model": llm_service.model,
        "available_models": models,
        "model_history": llm_service._model_history
    }


@router.post("/models/switch")
async def switch_model(req: ModelSwitchRequest):
    """Switch to a different Ollama model."""
    if not llm_service:
        raise HTTPException(503, "LLM service not initialized")
    result = llm_service.switch_model(req.model_name)
    return result


# --- Tools ---
@router.get("/tools")
async def list_tools():
    """List all available tools."""
    if not tool_registry:
        raise HTTPException(503, "Tool registry not initialized")
    return {
        "tools": tool_registry.get_tools_list(),
        "total": len(tool_registry.tools)
    }


@router.post("/tools/execute")
async def execute_tool(tool_name: str, params: dict = {}):
    """Manually execute a tool."""
    if not tool_registry:
        raise HTTPException(503, "Tool registry not initialized")
    if tool_name not in tool_registry.tools:
        raise HTTPException(404, f"Tool '{tool_name}' not found")
    result = tool_registry.tools[tool_name].execute(**params)
    return {"tool": tool_name, "result": result}


# --- Watch Folder ---
@router.get("/watch-folder/status")
async def watch_folder_status():
    """Get watch folder status."""
    if not watch_folder_service:
        raise HTTPException(503, "Watch folder service not initialized")
    return watch_folder_service.get_status()


@router.post("/watch-folder/scan")
async def scan_watch_folder():
    """Manually trigger a watch folder scan."""
    if not watch_folder_service:
        raise HTTPException(503, "Watch folder service not initialized")
    results = watch_folder_service.scan_once()
    return {"scanned": len(results), "results": results}


@router.post("/watch-folder/reset")
async def reset_watch_folder():
    """Reset watch folder tracking (re-index all files)."""
    if not watch_folder_service:
        raise HTTPException(503, "Watch folder service not initialized")
    watch_folder_service.reset()
    return {"status": "reset", "message": "All files will be re-indexed on next scan"}


# --- File Memory Store ---
@router.get("/memory-store/stats")
async def memory_store_stats():
    """Get file memory store statistics."""
    if not memory_service:
        raise HTTPException(503, "Memory service not initialized")
    return memory_service.get_stats()


@router.get("/memory-store/associations")
async def memory_associations(memory_id: str = None):
    """Get memory association graph or associations for a specific memory."""
    if not memory_service:
        raise HTTPException(503, "Memory service not initialized")
    if memory_id:
        return {"associations": memory_service.get_associations(memory_id)}
    return memory_service.get_association_graph()


@router.get("/info")
async def system_info():
    """Get overall system info."""
    info = {
        "version": "2.0.0",
        "features": [
            "File-system memory store",
            "Memory association graph",
            "Tool/Plugin system",
            "Query decomposition",
            "Auto-indexing watch folder",
            "Multi-model support",
            "Voice input",
            "Knowledge graph",
            "Sentiment analysis",
            "Topic clustering",
            "Follow-up suggestions",
            "Document summarization",
            "Conversation export"
        ]
    }
    if llm_service:
        info["current_model"] = llm_service.model
    if tool_registry:
        info["tools_count"] = len(tool_registry.tools)
    if watch_folder_service:
        info["watch_folder"] = watch_folder_service.get_status()
    if memory_service:
        info["memory_stats"] = memory_service.get_stats()
    return info
