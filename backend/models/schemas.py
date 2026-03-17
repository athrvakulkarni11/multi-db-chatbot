"""
Pydantic Schemas for API Request/Response validation
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# --- Chat Schemas ---

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    sources: list[dict] = []
    memories_used: list[dict] = []

class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: str
    metadata: dict = {}


# --- Conversation Schemas ---

class ConversationCreate(BaseModel):
    title: str = Field(default="New Conversation", max_length=200)

class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0
    summary: Optional[str] = None
    is_archived: int = 0

class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[int] = None


# --- Memory Schemas ---

class MemoryCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    memory_type: str = Field(default="semantic", pattern="^(episodic|semantic|procedural)$")
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = []

class MemoryOut(BaseModel):
    id: str
    content: str
    memory_type: str
    importance: float
    access_count: int = 0
    last_accessed: Optional[str] = None
    created_at: str
    tags: list = []
    decay_factor: float = 1.0
    is_consolidated: int = 0
    score: Optional[float] = None

class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    importance: Optional[float] = None
    tags: Optional[list[str]] = None

class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    memory_type: Optional[str] = None


# --- Document Schemas ---

class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int = 0
    title: Optional[str] = None
    description: Optional[str] = None
    chunk_count: int = 0
    created_at: str
    is_indexed: int = 0

class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    document_ids: Optional[list[str]] = None

class DocumentSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    content: str
    score: float
    chunk_index: int


# --- Analytics Schemas ---

class AnalyticsOverview(BaseModel):
    total_conversations: int = 0
    total_messages: int = 0
    total_memories: int = 0
    total_documents: int = 0
    total_document_chunks: int = 0
    memories_by_type: dict = {}
    documents_by_type: dict = {}
    messages_per_day: list[dict] = []
    average_memory_importance: float = 0.0
