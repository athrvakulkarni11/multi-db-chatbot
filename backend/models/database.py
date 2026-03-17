"""
SQLite Database Models and Connection Management
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from config import DB_PATH


def get_connection():
    """Get a SQLite database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database():
    """Initialize the database with all required tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Conversations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            message_count INTEGER DEFAULT 0,
            summary TEXT,
            is_archived INTEGER DEFAULT 0
        )
    """)

    # Messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            token_count INTEGER DEFAULT 0,
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)

    # Memories table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            memory_type TEXT NOT NULL DEFAULT 'episodic'
                CHECK(memory_type IN ('episodic', 'semantic', 'procedural')),
            importance REAL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            last_accessed TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            source_conversation_id TEXT,
            tags TEXT DEFAULT '[]',
            metadata TEXT DEFAULT '{}',
            decay_factor REAL DEFAULT 1.0,
            is_consolidated INTEGER DEFAULT 0,
            FOREIGN KEY (source_conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
        )
    """)

    # Documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            original_path TEXT,
            file_type TEXT NOT NULL,
            file_size INTEGER,
            title TEXT,
            author TEXT,
            description TEXT,
            chunk_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            metadata TEXT DEFAULT '{}',
            is_indexed INTEGER DEFAULT 0
        )
    """)

    # Document chunks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            content TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            start_char INTEGER,
            end_char INTEGER,
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    """)

    # Analytics events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analytics_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            event_data TEXT DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Create indices for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_type ON analytics_events(event_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_created ON analytics_events(created_at)")

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")


# --- CRUD Operations ---

class ConversationDB:
    @staticmethod
    def create(conv_id: str, title: str) -> dict:
        conn = get_connection()
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conv_id, title, now, now)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
        conn.close()
        return dict(row)

    @staticmethod
    def get(conv_id: str) -> dict | None:
        conn = get_connection()
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def list_all(include_archived=False) -> list[dict]:
        conn = get_connection()
        if include_archived:
            rows = conn.execute("SELECT * FROM conversations ORDER BY updated_at DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM conversations WHERE is_archived = 0 ORDER BY updated_at DESC"
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def update(conv_id: str, **kwargs) -> dict | None:
        conn = get_connection()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [conv_id]
        conn.execute(f"UPDATE conversations SET {sets}, updated_at = datetime('now') WHERE id = ?", values)
        conn.commit()
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def delete(conv_id: str):
        conn = get_connection()
        conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        conn.commit()
        conn.close()


class MessageDB:
    @staticmethod
    def create(msg_id: str, conversation_id: str, role: str, content: str, metadata: dict = None) -> dict:
        conn = get_connection()
        now = datetime.utcnow().isoformat()
        meta_str = json.dumps(metadata or {})
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, conversation_id, role, content, now, meta_str)
        )
        conn.execute(
            "UPDATE conversations SET message_count = message_count + 1, updated_at = ? WHERE id = ?",
            (now, conversation_id)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)).fetchone()
        conn.close()
        return dict(row)

    @staticmethod
    def get_by_conversation(conversation_id: str, limit: int = 100) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?",
            (conversation_id, limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def count_by_conversation(conversation_id: str) -> int:
        conn = get_connection()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE conversation_id = ?",
            (conversation_id,)
        ).fetchone()
        conn.close()
        return row["cnt"]


class MemoryDB:
    @staticmethod
    def create(mem_id: str, content: str, memory_type: str = "episodic",
               importance: float = 0.5, source_conversation_id: str = None,
               tags: list = None, metadata: dict = None) -> dict:
        conn = get_connection()
        now = datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO memories 
            (id, content, memory_type, importance, created_at, updated_at, 
             source_conversation_id, tags, metadata) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mem_id, content, memory_type, importance, now, now,
             source_conversation_id, json.dumps(tags or []), json.dumps(metadata or {}))
        )
        conn.commit()
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        conn.close()
        return dict(row)

    @staticmethod
    def get(mem_id: str) -> dict | None:
        conn = get_connection()
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def list_all(memory_type: str = None, limit: int = 50) -> list[dict]:
        conn = get_connection()
        if memory_type:
            rows = conn.execute(
                "SELECT * FROM memories WHERE memory_type = ? ORDER BY importance DESC, created_at DESC LIMIT ?",
                (memory_type, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY importance DESC, created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def update_access(mem_id: str):
        conn = get_connection()
        conn.execute(
            "UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id = ?",
            (mem_id,)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def apply_decay(decay_rate: float = 0.01):
        conn = get_connection()
        conn.execute(
            """UPDATE memories SET decay_factor = MAX(0.1, decay_factor - ?)
            WHERE is_consolidated = 0""",
            (decay_rate,)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def delete(mem_id: str):
        conn = get_connection()
        conn.execute("DELETE FROM memories WHERE id = ?", (mem_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_stats() -> dict:
        conn = get_connection()
        total = conn.execute("SELECT COUNT(*) as cnt FROM memories").fetchone()["cnt"]
        by_type = conn.execute(
            "SELECT memory_type, COUNT(*) as cnt FROM memories GROUP BY memory_type"
        ).fetchall()
        avg_importance = conn.execute(
            "SELECT AVG(importance) as avg_imp FROM memories"
        ).fetchone()["avg_imp"]
        conn.close()
        return {
            "total": total,
            "by_type": {r["memory_type"]: r["cnt"] for r in by_type},
            "average_importance": round(avg_importance, 3) if avg_importance else 0
        }


class DocumentDB:
    @staticmethod
    def create(doc_id: str, filename: str, file_type: str, file_size: int = 0,
               title: str = None, metadata: dict = None) -> dict:
        conn = get_connection()
        now = datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO documents 
            (id, filename, file_type, file_size, title, created_at, metadata) 
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (doc_id, filename, file_type, file_size, title or filename, now, json.dumps(metadata or {}))
        )
        conn.commit()
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        conn.close()
        return dict(row)

    @staticmethod
    def get(doc_id: str) -> dict | None:
        conn = get_connection()
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def list_all() -> list[dict]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def update(doc_id: str, **kwargs) -> dict | None:
        conn = get_connection()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [doc_id]
        conn.execute(f"UPDATE documents SET {sets} WHERE id = ?", values)
        conn.commit()
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def delete(doc_id: str):
        conn = get_connection()
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_stats() -> dict:
        conn = get_connection()
        total = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()["cnt"]
        indexed = conn.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE is_indexed = 1"
        ).fetchone()["cnt"]
        by_type = conn.execute(
            "SELECT file_type, COUNT(*) as cnt FROM documents GROUP BY file_type"
        ).fetchall()
        total_chunks = conn.execute(
            "SELECT COUNT(*) as cnt FROM document_chunks"
        ).fetchone()["cnt"]
        conn.close()
        return {
            "total": total,
            "indexed": indexed,
            "by_type": {r["file_type"]: r["cnt"] for r in by_type},
            "total_chunks": total_chunks
        }


class ChunkDB:
    @staticmethod
    def create_many(chunks: list[dict]):
        conn = get_connection()
        for c in chunks:
            conn.execute(
                """INSERT INTO document_chunks 
                (id, document_id, content, chunk_index, start_char, end_char, metadata) 
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (c["id"], c["document_id"], c["content"], c["chunk_index"],
                 c.get("start_char", 0), c.get("end_char", 0), json.dumps(c.get("metadata", {})))
            )
        conn.commit()
        conn.close()

    @staticmethod
    def get_by_document(document_id: str) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM document_chunks WHERE document_id = ? ORDER BY chunk_index",
            (document_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get(chunk_id: str) -> dict | None:
        conn = get_connection()
        row = conn.execute("SELECT * FROM document_chunks WHERE id = ?", (chunk_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_many(chunk_ids: list[str]) -> list[dict]:
        conn = get_connection()
        placeholders = ",".join("?" for _ in chunk_ids)
        rows = conn.execute(
            f"SELECT * FROM document_chunks WHERE id IN ({placeholders})",
            chunk_ids
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


class AnalyticsDB:
    @staticmethod
    def log_event(event_type: str, event_data: dict = None):
        conn = get_connection()
        conn.execute(
            "INSERT INTO analytics_events (event_type, event_data) VALUES (?, ?)",
            (event_type, json.dumps(event_data or {}))
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_events(event_type: str = None, days: int = 30, limit: int = 100) -> list[dict]:
        conn = get_connection()
        if event_type:
            rows = conn.execute(
                """SELECT * FROM analytics_events 
                WHERE event_type = ? AND created_at >= datetime('now', ?) 
                ORDER BY created_at DESC LIMIT ?""",
                (event_type, f'-{days} days', limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM analytics_events 
                WHERE created_at >= datetime('now', ?) 
                ORDER BY created_at DESC LIMIT ?""",
                (f'-{days} days', limit)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_daily_counts(event_type: str = None, days: int = 30) -> list[dict]:
        conn = get_connection()
        if event_type:
            rows = conn.execute(
                """SELECT DATE(created_at) as date, COUNT(*) as count 
                FROM analytics_events 
                WHERE event_type = ? AND created_at >= datetime('now', ?)
                GROUP BY DATE(created_at) ORDER BY date""",
                (event_type, f'-{days} days')
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT DATE(created_at) as date, COUNT(*) as count 
                FROM analytics_events 
                WHERE created_at >= datetime('now', ?)
                GROUP BY DATE(created_at) ORDER BY date""",
                (f'-{days} days',)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
