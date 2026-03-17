"""
Memory Service — Manages persistent long-term memory with semantic retrieval
"""
import uuid
import json
from datetime import datetime
from models.database import MemoryDB
from services.search_service import SearchService
from services.llm_service import LLMService
from config import MAX_CONTEXT_MEMORIES, MEMORY_DECAY_RATE
import logging

logger = logging.getLogger(__name__)

MEMORY_INDEX = "memories"


class MemoryService:
    def __init__(self, search_service: SearchService, llm_service: LLMService):
        self.search_service = search_service
        self.llm_service = llm_service
        self._load_existing_memories()

    def _load_existing_memories(self):
        """Load existing memories into the search index on startup."""
        memories = MemoryDB.list_all(limit=10000)
        if memories:
            items = [{"id": m["id"], "text": m["content"]} for m in memories]
            self.search_service.add_batch_to_index(MEMORY_INDEX, items)
            logger.info(f"Loaded {len(memories)} memories into search index")

    def create_memory(self, content: str, memory_type: str = "episodic",
                      importance: float = None, source_conversation_id: str = None,
                      tags: list[str] = None) -> dict:
        """Create a new memory with embedding."""
        mem_id = str(uuid.uuid4())

        # Auto-rate importance if not provided
        if importance is None:
            importance = self.llm_service.extract_importance(content)

        memory = MemoryDB.create(
            mem_id=mem_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            source_conversation_id=source_conversation_id,
            tags=tags
        )

        # Add to vector index
        self.search_service.add_to_index(MEMORY_INDEX, mem_id, content)

        logger.info(f"Created memory {mem_id} (importance: {importance:.2f})")
        return memory

    def search_memories(self, query: str, top_k: int = MAX_CONTEXT_MEMORIES,
                        memory_type: str = None) -> list[dict]:
        """Search for relevant memories using hybrid search."""
        results = self.search_service.hybrid_search(MEMORY_INDEX, query, top_k=top_k * 2)

        memories = []
        for result in results:
            memory = MemoryDB.get(result["id"])
            if memory:
                # Filter by type if specified
                if memory_type and memory["memory_type"] != memory_type:
                    continue

                # Apply decay factor to score
                adjusted_score = result["score"] * memory["decay_factor"]
                memory["score"] = adjusted_score

                # Update access tracking
                MemoryDB.update_access(memory["id"])
                memories.append(memory)

        # Sort by adjusted score and return top K
        memories.sort(key=lambda m: m["score"], reverse=True)
        return memories[:top_k]

    def get_relevant_context(self, query: str) -> list[dict]:
        """Get relevant memories for building conversation context."""
        return self.search_memories(query, top_k=MAX_CONTEXT_MEMORIES)

    def auto_extract_memories(self, user_message: str, assistant_response: str,
                              conversation_id: str = None):
        """Automatically extract and store memories from a conversation exchange."""
        extracted = self.llm_service.extract_memories(user_message, assistant_response)
        for fact in extracted:
            self.create_memory(
                content=fact,
                memory_type="episodic",
                source_conversation_id=conversation_id
            )
        if extracted:
            logger.info(f"Auto-extracted {len(extracted)} memories")
        return extracted

    def consolidate_memories(self, conversation_id: str, messages: list[dict]):
        """Consolidate conversation memories into a summary."""
        summary = self.llm_service.summarize_conversation(messages)
        if summary:
            self.create_memory(
                content=f"Conversation summary: {summary}",
                memory_type="semantic",
                importance=0.7,
                source_conversation_id=conversation_id
            )
            logger.info(f"Consolidated memories for conversation {conversation_id}")

    def apply_memory_decay(self):
        """Apply time-based decay to all memories."""
        MemoryDB.apply_decay(MEMORY_DECAY_RATE)
        logger.info("Applied memory decay")

    def get_all_memories(self, memory_type: str = None, limit: int = 50) -> list[dict]:
        """Get all memories, optionally filtered by type."""
        memories = MemoryDB.list_all(memory_type=memory_type, limit=limit)
        for m in memories:
            m["tags"] = json.loads(m["tags"]) if isinstance(m["tags"], str) else m["tags"]
        return memories

    def delete_memory(self, memory_id: str):
        """Delete a memory from database and search index."""
        MemoryDB.delete(memory_id)
        self.search_service.remove_from_index(MEMORY_INDEX, memory_id)
        logger.info(f"Deleted memory {memory_id}")

    def get_stats(self) -> dict:
        """Get memory statistics."""
        return MemoryDB.get_stats()
