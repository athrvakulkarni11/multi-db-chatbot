"""
File-System Memory Store — Human-readable JSON-based persistent memory

Stores memories as individual JSON files in a structured directory hierarchy:
  data/memory_store/
    ├── episodic/
    │   ├── 2026-03-19_abc123.json
    │   └── ...
    ├── semantic/
    ├── procedural/
    ├── associations.json      ← memory-to-memory links
    └── index.json             ← fast lookup index
"""
import json
import uuid
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from config import DATA_DIR
import logging

logger = logging.getLogger(__name__)

MEMORY_STORE_DIR = DATA_DIR / "memory_store"
ASSOCIATION_FILE = MEMORY_STORE_DIR / "associations.json"
INDEX_FILE = MEMORY_STORE_DIR / "index.json"


class FileMemoryStore:
    """
    Persistent file-system memory that stores each memory as a 
    human-readable JSON file. Features:
    - Directory-based organization by memory type
    - Individual JSON files per memory (inspectable/editable)
    - Association graph between related memories
    - Fast in-memory index synced to disk
    """

    def __init__(self):
        self.index: dict[str, dict] = {}  # mem_id -> {path, type, importance, created_at, ...}
        self.associations: dict[str, list[dict]] = {}  # mem_id -> [{target_id, relation, strength}]
        self._init_directories()
        self._load_index()
        self._load_associations()

    def _init_directories(self):
        """Create directory structure for memory types."""
        for mem_type in ["episodic", "semantic", "procedural"]:
            (MEMORY_STORE_DIR / mem_type).mkdir(parents=True, exist_ok=True)

    def _load_index(self):
        """Load the fast-lookup index from disk."""
        if INDEX_FILE.exists():
            try:
                with open(INDEX_FILE, "r", encoding="utf-8") as f:
                    self.index = json.load(f)
                logger.info(f"Loaded memory index: {len(self.index)} entries")
            except Exception as e:
                logger.error(f"Error loading memory index: {e}")
                self.index = {}
                self._rebuild_index()
        else:
            self._rebuild_index()

    def _save_index(self):
        """Persist the index to disk."""
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(self.index, f, indent=2, default=str)

    def _load_associations(self):
        """Load association graph from disk."""
        if ASSOCIATION_FILE.exists():
            try:
                with open(ASSOCIATION_FILE, "r", encoding="utf-8") as f:
                    self.associations = json.load(f)
                total_links = sum(len(v) for v in self.associations.values())
                logger.info(f"Loaded memory associations: {total_links} links")
            except Exception as e:
                logger.error(f"Error loading associations: {e}")
                self.associations = {}
        else:
            self.associations = {}

    def _save_associations(self):
        """Persist association graph to disk."""
        with open(ASSOCIATION_FILE, "w", encoding="utf-8") as f:
            json.dump(self.associations, f, indent=2, default=str)

    def _rebuild_index(self):
        """Rebuild index by scanning all memory files on disk."""
        logger.info("Rebuilding memory index from files...")
        self.index = {}
        for mem_type in ["episodic", "semantic", "procedural"]:
            type_dir = MEMORY_STORE_DIR / mem_type
            if not type_dir.exists():
                continue
            for file_path in type_dir.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    mem_id = data.get("id", file_path.stem)
                    self.index[mem_id] = {
                        "path": str(file_path.relative_to(MEMORY_STORE_DIR)),
                        "type": mem_type,
                        "importance": data.get("importance", 0.5),
                        "decay_factor": data.get("decay_factor", 1.0),
                        "created_at": data.get("created_at", ""),
                        "content_preview": data.get("content", "")[:100],
                        "access_count": data.get("access_count", 0),
                        "tags": data.get("tags", [])
                    }
                except Exception as e:
                    logger.error(f"Error reading memory file {file_path}: {e}")
        self._save_index()
        logger.info(f"Rebuilt index: {len(self.index)} memories found")

    def _memory_filename(self, mem_id: str, created_at: str) -> str:
        """Generate a human-readable filename: YYYY-MM-DD_shortid.json"""
        date_part = created_at[:10] if created_at else datetime.utcnow().strftime("%Y-%m-%d")
        short_id = mem_id[:8]
        return f"{date_part}_{short_id}.json"

    # ==================== CRUD ====================

    def save_memory(self, memory: dict) -> dict:
        """
        Save a memory to the file system.
        
        Args:
            memory: dict with keys: id, content, memory_type, importance,
                    tags, source_conversation_id, metadata, etc.
        Returns:
            The saved memory dict with file path info added.
        """
        mem_id = memory.get("id", str(uuid.uuid4()))
        mem_type = memory.get("memory_type", "episodic")
        created_at = memory.get("created_at", datetime.utcnow().isoformat())

        # Build the file data
        file_data = {
            "id": mem_id,
            "content": memory.get("content", ""),
            "memory_type": mem_type,
            "importance": memory.get("importance", 0.5),
            "decay_factor": memory.get("decay_factor", 1.0),
            "access_count": memory.get("access_count", 0),
            "last_accessed": memory.get("last_accessed"),
            "created_at": created_at,
            "updated_at": datetime.utcnow().isoformat(),
            "source_conversation_id": memory.get("source_conversation_id"),
            "tags": memory.get("tags", []),
            "metadata": memory.get("metadata", {}),
            "is_consolidated": memory.get("is_consolidated", False)
        }

        # Write to file
        filename = self._memory_filename(mem_id, created_at)
        file_path = MEMORY_STORE_DIR / mem_type / filename
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(file_data, f, indent=2, ensure_ascii=False, default=str)

        # Update index
        self.index[mem_id] = {
            "path": str(file_path.relative_to(MEMORY_STORE_DIR)),
            "type": mem_type,
            "importance": file_data["importance"],
            "decay_factor": file_data["decay_factor"],
            "created_at": created_at,
            "content_preview": file_data["content"][:100],
            "access_count": file_data["access_count"],
            "tags": file_data["tags"]
        }
        self._save_index()

        logger.info(f"Saved memory {mem_id} to {file_path}")
        return file_data

    def get_memory(self, mem_id: str) -> Optional[dict]:
        """Read a memory from its JSON file."""
        if mem_id not in self.index:
            return None

        file_path = MEMORY_STORE_DIR / self.index[mem_id]["path"]
        if not file_path.exists():
            # File was deleted externally, clean up index
            del self.index[mem_id]
            self._save_index()
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading memory {mem_id}: {e}")
            return None

    def update_memory(self, mem_id: str, **updates) -> Optional[dict]:
        """Update specific fields of a memory."""
        memory = self.get_memory(mem_id)
        if not memory:
            return None

        memory.update(updates)
        memory["updated_at"] = datetime.utcnow().isoformat()
        return self.save_memory(memory)

    def delete_memory(self, mem_id: str) -> bool:
        """Delete a memory file and remove from index."""
        if mem_id not in self.index:
            return False

        file_path = MEMORY_STORE_DIR / self.index[mem_id]["path"]
        if file_path.exists():
            file_path.unlink()

        del self.index[mem_id]
        self._save_index()

        # Clean up associations
        self.associations.pop(mem_id, None)
        for key in list(self.associations.keys()):
            self.associations[key] = [
                a for a in self.associations[key] if a["target_id"] != mem_id
            ]
        self._save_associations()

        logger.info(f"Deleted memory {mem_id}")
        return True

    def list_memories(self, memory_type: str = None, limit: int = 50) -> list[dict]:
        """List memories from index (fast) or read full data."""
        entries = []
        for mem_id, info in self.index.items():
            if memory_type and info["type"] != memory_type:
                continue
            entries.append({"id": mem_id, **info})

        # Sort by importance descending, then created_at descending
        entries.sort(key=lambda x: (x.get("importance", 0), x.get("created_at", "")), reverse=True)
        return entries[:limit]

    def get_all_full_memories(self, memory_type: str = None, limit: int = 200) -> list[dict]:
        """Read full memory data for all memories (slower but complete)."""
        entries = self.list_memories(memory_type, limit)
        memories = []
        for entry in entries:
            mem = self.get_memory(entry["id"])
            if mem:
                memories.append(mem)
        return memories

    def record_access(self, mem_id: str):
        """Record that a memory was accessed (bump access count)."""
        if mem_id in self.index:
            self.index[mem_id]["access_count"] = self.index[mem_id].get("access_count", 0) + 1
            # Also update the file
            memory = self.get_memory(mem_id)
            if memory:
                memory["access_count"] = memory.get("access_count", 0) + 1
                memory["last_accessed"] = datetime.utcnow().isoformat()
                self.save_memory(memory)

    def apply_decay(self, rate: float = 0.01):
        """Apply time-based decay to all non-consolidated memories."""
        for mem_id, info in self.index.items():
            if info.get("decay_factor", 1.0) > 0.1:
                new_decay = max(0.1, info.get("decay_factor", 1.0) - rate)
                info["decay_factor"] = new_decay
        self._save_index()
        logger.info("Applied memory decay to file store")

    # ==================== Associations ====================

    def add_association(self, source_id: str, target_id: str,
                       relation: str = "related_to", strength: float = 0.5):
        """Create an association (link) between two memories."""
        if source_id not in self.index or target_id not in self.index:
            return

        if source_id not in self.associations:
            self.associations[source_id] = []

        # Check for existing
        for assoc in self.associations[source_id]:
            if assoc["target_id"] == target_id:
                assoc["strength"] = min(1.0, assoc["strength"] + 0.1)  # Strengthen existing
                self._save_associations()
                return

        self.associations[source_id].append({
            "target_id": target_id,
            "relation": relation,
            "strength": strength,
            "created_at": datetime.utcnow().isoformat()
        })
        self._save_associations()
        logger.debug(f"Associated memory {source_id[:8]} -> {target_id[:8]} ({relation})")

    def get_associations(self, mem_id: str) -> list[dict]:
        """Get all associations for a memory (outgoing + incoming)."""
        outgoing = self.associations.get(mem_id, [])
        incoming = []
        for source_id, links in self.associations.items():
            if source_id == mem_id:
                continue
            for link in links:
                if link["target_id"] == mem_id:
                    incoming.append({
                        "target_id": source_id,
                        "relation": f"inverse_{link['relation']}",
                        "strength": link["strength"]
                    })
        return outgoing + incoming

    def get_association_graph(self) -> dict:
        """Get the full association graph for visualization."""
        nodes = []
        for mem_id, info in self.index.items():
            nodes.append({
                "id": mem_id,
                "label": info.get("content_preview", "")[:40],
                "type": info["type"],
                "importance": info.get("importance", 0.5)
            })

        edges = []
        for source_id, links in self.associations.items():
            for link in links:
                edges.append({
                    "source": source_id,
                    "target": link["target_id"],
                    "relation": link["relation"],
                    "strength": link["strength"]
                })

        return {"nodes": nodes, "edges": edges}

    # ==================== Stats ====================

    def get_stats(self) -> dict:
        """Get statistics about the memory store."""
        total = len(self.index)
        by_type = {}
        total_importance = 0
        for info in self.index.values():
            t = info["type"]
            by_type[t] = by_type.get(t, 0) + 1
            total_importance += info.get("importance", 0.5)

        total_associations = sum(len(v) for v in self.associations.values())
        disk_size = sum(
            f.stat().st_size for f in MEMORY_STORE_DIR.rglob("*.json")
        )

        return {
            "total": total,
            "by_type": by_type,
            "average_importance": round(total_importance / total, 3) if total else 0,
            "total_associations": total_associations,
            "disk_size_bytes": disk_size,
            "disk_size_human": self._human_size(disk_size),
            "store_path": str(MEMORY_STORE_DIR)
        }

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
