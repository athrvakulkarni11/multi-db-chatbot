"""
Auto-Indexing Watch Folder — Monitors a directory for new documents and auto-indexes them

Drop files into data/watch_folder/ and they will be automatically
detected, parsed, chunked, embedded, and indexed for RAG — no upload needed.
"""
import time
import threading
from pathlib import Path
from config import DATA_DIR
import logging

logger = logging.getLogger(__name__)

WATCH_DIR = DATA_DIR / "watch_folder"
WATCH_DIR.mkdir(exist_ok=True)

PROCESSED_FILE = WATCH_DIR / ".processed.json"

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv"}


class WatchFolderService:
    """
    Watches a local directory for new files and auto-indexes them.
    Uses background polling (no native OS watchers needed).
    """

    def __init__(self, document_service):
        self.document_service = document_service
        self.processed: set[str] = set()
        self.watch_thread: threading.Thread = None
        self.running = False
        self._load_processed()

    def _load_processed(self):
        """Load the set of already-processed files."""
        if PROCESSED_FILE.exists():
            try:
                import json
                with open(PROCESSED_FILE, "r") as f:
                    self.processed = set(json.load(f))
            except Exception:
                self.processed = set()

    def _save_processed(self):
        """Save the processed file list."""
        import json
        with open(PROCESSED_FILE, "w") as f:
            json.dump(list(self.processed), f)

    def scan_once(self) -> list[dict]:
        """Scan the watch folder once and index any new files."""
        results = []
        for file_path in WATCH_DIR.iterdir():
            if file_path.name.startswith("."):
                continue
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if str(file_path) in self.processed:
                continue

            logger.info(f"Auto-indexing: {file_path.name}")
            try:
                result = self.document_service.process_local_file(str(file_path))
                self.processed.add(str(file_path))
                self._save_processed()
                results.append({
                    "filename": file_path.name,
                    "status": "indexed",
                    "chunks": result.get("chunk_count", 0)
                })
                logger.info(f"Auto-indexed: {file_path.name}")
            except Exception as e:
                logger.error(f"Auto-index error for {file_path.name}: {e}")
                results.append({
                    "filename": file_path.name,
                    "status": "error",
                    "error": str(e)
                })

        return results

    def start_watching(self, interval: int = 10):
        """Start background watch thread."""
        if self.running:
            return

        self.running = True
        def _watch_loop():
            logger.info(f"Watch folder active: {WATCH_DIR}")
            while self.running:
                try:
                    self.scan_once()
                except Exception as e:
                    logger.error(f"Watch folder error: {e}")
                time.sleep(interval)

        self.watch_thread = threading.Thread(target=_watch_loop, daemon=True)
        self.watch_thread.start()

    def stop_watching(self):
        """Stop the background watch thread."""
        self.running = False
        if self.watch_thread:
            self.watch_thread.join(timeout=5)

    def get_status(self) -> dict:
        """Get watch folder status."""
        pending = []
        for file_path in WATCH_DIR.iterdir():
            if file_path.name.startswith("."):
                continue
            if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                pending.append({
                    "filename": file_path.name,
                    "size": file_path.stat().st_size,
                    "processed": str(file_path) in self.processed
                })
        return {
            "watch_dir": str(WATCH_DIR),
            "is_running": self.running,
            "total_files": len(pending),
            "processed": len([f for f in pending if f["processed"]]),
            "pending": len([f for f in pending if not f["processed"]]),
            "files": pending
        }

    def reset(self):
        """Reset processed file tracking (will re-index everything)."""
        self.processed.clear()
        self._save_processed()
