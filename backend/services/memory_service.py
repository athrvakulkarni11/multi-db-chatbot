"""
Memory Service — Manages persistent long-term memory with dual storage
(SQLite + File System) and semantic retrieval with memory associations
"""
import uuid
import json
from datetime import datetime
from models.database import MemoryDB
from services.search_service import SearchService
from services.llm_service import LLMService
from services.file_memory_store import FileMemoryStore
from config import MAX_CONTEXT_MEMORIES, MEMORY_DECAY_RATE
import logging

logger = logging.getLogger(__name__)

MEMORY_INDEX = "memories"


class MemoryService:
    def __init__(self, search_service: SearchService, llm_service: LLMService):
        self.search_service = search_service
        self.llm_service = llm_service
        self.file_store = FileMemoryStore()  # File-system based store
        self._load_existing_memories()

    def _load_existing_memories(self):
        """Load existing memories into the search index on startup."""
        # Load from file store first (source of truth)
        file_memories = self.file_store.get_all_full_memories(limit=10000)
        if file_memories:
            items = [{"id": m["id"], "text": m["content"]} for m in file_memories]
            self.search_service.add_batch_to_index(MEMORY_INDEX, items)
            logger.info(f"Loaded {len(file_memories)} memories from file store into search index")
            return

        # Fallback: load from SQLite (for migration)
        memories = MemoryDB.list_all(limit=10000)
        if memories:
            items = [{"id": m["id"], "text": m["content"]} for m in memories]
            self.search_service.add_batch_to_index(MEMORY_INDEX, items)
            # Migrate to file store
            for m in memories:
                m["tags"] = json.loads(m["tags"]) if isinstance(m.get("tags"), str) else m.get("tags", [])
                self.file_store.save_memory(m)
            logger.info(f"Migrated {len(memories)} memories from SQLite to file store")

    def create_memory(self, content: str, memory_type: str = "episodic",
                      importance: float = None, source_conversation_id: str = None,
                      tags: list[str] = None) -> dict:
        """Create a new memory with embedding and file storage."""
        mem_id = str(uuid.uuid4())

        # Auto-rate importance if not provided
        if importance is None:
            importance = self.llm_service.extract_importance(content)

        memory_data = {
            "id": mem_id,
            "content": content,
            "memory_type": memory_type,
            "importance": importance,
            "source_conversation_id": source_conversation_id,
            "tags": tags or [],
            "created_at": datetime.utcnow().isoformat(),
            "decay_factor": 1.0,
            "access_count": 0,
            "is_consolidated": False
        }

        # Save to file system (primary store)
        self.file_store.save_memory(memory_data)

        # Also save to SQLite (for backward compat / analytics queries)
        try:
            MemoryDB.create(
                mem_id=mem_id, content=content, memory_type=memory_type,
                importance=importance, source_conversation_id=source_conversation_id,
                tags=tags
            )
        except Exception as e:
            logger.debug(f"SQLite save (non-critical): {e}")

        # Add to vector index
        self.search_service.add_to_index(MEMORY_INDEX, mem_id, content)

        # Auto-detect associations with existing memories
        self._auto_associate(mem_id, content)

        logger.info(f"Created memory {mem_id} (importance: {importance:.2f})")
        return memory_data

    def _auto_associate(self, new_mem_id: str, content: str):
        """Automatically link a new memory to semantically similar existing ones."""
        try:
            results = self.search_service.semantic_search(MEMORY_INDEX, content, top_k=3)
            for result in results:
                if result["id"] != new_mem_id and result["score"] > 0.6:
                    self.file_store.add_association(
                        new_mem_id, result["id"],
                        relation="semantically_related",
                        strength=min(1.0, result["score"])
                    )
        except Exception as e:
            logger.debug(f"Auto-association error: {e}")

    def search_memories(self, query: str, top_k: int = MAX_CONTEXT_MEMORIES,
                        memory_type: str = None) -> list[dict]:
        """Search for relevant memories using hybrid search."""
        results = self.search_service.hybrid_search(MEMORY_INDEX, query, top_k=top_k * 2)

        memories = []
        for result in results:
            memory = self.file_store.get_memory(result["id"])
            if not memory:
                # Fallback to SQLite
                memory = MemoryDB.get(result["id"])
            if memory:
                if memory_type and memory.get("memory_type") != memory_type:
                    continue

                # Apply decay factor to score
                decay = memory.get("decay_factor", 1.0)
                adjusted_score = result["score"] * decay
                memory["score"] = adjusted_score

                # Update access tracking
                self.file_store.record_access(memory["id"])
                try:
                    MemoryDB.update_access(memory["id"])
                except Exception:
                    pass
                memories.append(memory)

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
        self.file_store.apply_decay(MEMORY_DECAY_RATE)
        try:
            MemoryDB.apply_decay(MEMORY_DECAY_RATE)
        except Exception:
            pass
        logger.info("Applied memory decay")

    def get_all_memories(self, memory_type: str = None, limit: int = 50) -> list[dict]:
        """Get all memories from file store."""
        memories = self.file_store.get_all_full_memories(memory_type=memory_type, limit=limit)
        if not memories:
            # Fallback to SQLite
            memories = MemoryDB.list_all(memory_type=memory_type, limit=limit)
            for m in memories:
                m["tags"] = json.loads(m["tags"]) if isinstance(m.get("tags"), str) else m.get("tags", [])
        return memories

    def delete_memory(self, memory_id: str):
        """Delete a memory from all stores."""
        self.file_store.delete_memory(memory_id)
        try:
            MemoryDB.delete(memory_id)
        except Exception:
            pass
        self.search_service.remove_from_index(MEMORY_INDEX, memory_id)
        logger.info(f"Deleted memory {memory_id}")

    def get_stats(self) -> dict:
        """Get memory statistics from file store."""
        file_stats = self.file_store.get_stats()
        # Merge with SQLite stats for completeness
        try:
            db_stats = MemoryDB.get_stats()
            file_stats["db_total"] = db_stats.get("total", 0)
        except Exception:
            pass
        return file_stats

    def get_associations(self, memory_id: str) -> list[dict]:
        """Get associations for a memory."""
        return self.file_store.get_associations(memory_id)

    def get_association_graph(self) -> dict:
        """Get the full memory association graph."""
        return self.file_store.get_association_graph()
