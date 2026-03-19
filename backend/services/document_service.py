"""
Document Service — Document ingestion, parsing, chunking, and indexing
"""
import os
import uuid
import shutil
from pathlib import Path
from PyPDF2 import PdfReader
from docx import Document as DocxDocument
import markdown
from bs4 import BeautifulSoup
from models.database import DocumentDB, ChunkDB
from services.search_service import SearchService
from utils.chunker import chunk_text
from utils.text_processor import clean_text, extract_keywords
from config import UPLOAD_DIR
import logging

logger = logging.getLogger(__name__)

DOCUMENT_INDEX = "documents"


class DocumentService:
    def __init__(self, search_service: SearchService):
        self.search_service = search_service
        self._load_existing_documents()

    def _load_existing_documents(self):
        """Load existing document chunks into search index on startup."""
        documents = DocumentDB.list_all()
        indexed_docs = [d for d in documents if d["is_indexed"]]
        total_chunks = 0
        for doc in indexed_docs:
            chunks = ChunkDB.get_by_document(doc["id"])
            if chunks:
                items = [{"id": c["id"], "text": c["content"]} for c in chunks]
                self.search_service.add_batch_to_index(DOCUMENT_INDEX, items)
                total_chunks += len(chunks)
        if total_chunks:
            logger.info(f"Loaded {total_chunks} document chunks from {len(indexed_docs)} documents")

    def upload_document(self, filename: str, file_content: bytes) -> dict:
        """Upload and process a document."""
        doc_id = str(uuid.uuid4())
        file_ext = Path(filename).suffix.lower()

        # Save file to uploads directory
        save_path = UPLOAD_DIR / f"{doc_id}{file_ext}"
        with open(save_path, "wb") as f:
            f.write(file_content)

        # Determine file type
        type_map = {
            ".pdf": "pdf",
            ".docx": "docx",
            ".doc": "docx",
            ".txt": "txt",
            ".md": "markdown",
            ".csv": "csv"
        }
        file_type = type_map.get(file_ext, "txt")

        # Create database record
        doc = DocumentDB.create(
            doc_id=doc_id,
            filename=filename,
            file_type=file_type,
            file_size=len(file_content),
            title=Path(filename).stem
        )

        # Extract text and index
        try:
            text = self._extract_text(save_path, file_type)
            if text:
                self._index_document(doc_id, text)
                keywords = extract_keywords(text)
                DocumentDB.update(doc_id, is_indexed=1,
                                  metadata=str({"keywords": keywords}))
                doc = DocumentDB.get(doc_id)
            logger.info(f"Uploaded and indexed document: {filename}")
        except Exception as e:
            logger.error(f"Error indexing document {filename}: {e}")

        return doc

    def _extract_text(self, file_path: Path, file_type: str) -> str:
        """Extract text content from various file formats."""
        try:
            if file_type == "pdf":
                return self._extract_pdf(file_path)
            elif file_type == "docx":
                return self._extract_docx(file_path)
            elif file_type == "markdown":
                return self._extract_markdown(file_path)
            elif file_type == "csv":
                return self._extract_csv(file_path)
            else:
                return self._extract_txt(file_path)
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return ""

    def _extract_pdf(self, file_path: Path) -> str:
        """Extract text from PDF."""
        reader = PdfReader(str(file_path))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n\n".join(text_parts)

    def _extract_docx(self, file_path: Path) -> str:
        """Extract text from DOCX."""
        doc = DocxDocument(str(file_path))
        text_parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)
        return "\n\n".join(text_parts)

    def _extract_markdown(self, file_path: Path) -> str:
        """Extract text from Markdown."""
        with open(file_path, "r", encoding="utf-8") as f:
            md_content = f.read()
        html = markdown.markdown(md_content)
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n\n")

    def _extract_txt(self, file_path: Path) -> str:
        """Extract text from plain text file."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _extract_csv(self, file_path: Path) -> str:
        """Extract text from CSV, converting rows to readable text."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return content

    def _index_document(self, doc_id: str, text: str):
        """Chunk and index a document."""
        text = clean_text(text)
        chunks = chunk_text(text, strategy="paragraph")

        # Store chunks in database
        chunk_records = []
        search_items = []
        for chunk in chunks:
            chunk_id = str(uuid.uuid4())
            chunk_records.append({
                "id": chunk_id,
                "document_id": doc_id,
                "content": chunk["content"],
                "chunk_index": chunk["chunk_index"],
                "start_char": chunk["start_char"],
                "end_char": chunk["end_char"]
            })
            search_items.append({
                "id": chunk_id,
                "text": chunk["content"]
            })

        ChunkDB.create_many(chunk_records)
        self.search_service.add_batch_to_index(DOCUMENT_INDEX, search_items)

        # Update document chunk count
        DocumentDB.update(doc_id, chunk_count=len(chunks))
        logger.info(f"Indexed document {doc_id} into {len(chunks)} chunks")

    def search_documents(self, query: str, top_k: int = 5,
                         document_ids: list[str] = None) -> list[dict]:
        """Search across indexed documents."""
        results = self.search_service.hybrid_search(DOCUMENT_INDEX, query, top_k=top_k * 2)

        search_results = []
        for result in results:
            chunk = ChunkDB.get(result["id"])
            if not chunk:
                continue

            # Filter by document IDs if specified
            if document_ids and chunk["document_id"] not in document_ids:
                continue

            doc = DocumentDB.get(chunk["document_id"])
            if doc:
                search_results.append({
                    "chunk_id": result["id"],
                    "document_id": chunk["document_id"],
                    "document_name": doc["filename"],
                    "content": chunk["content"],
                    "score": result["score"],
                    "chunk_index": chunk["chunk_index"]
                })

        search_results.sort(key=lambda x: x["score"], reverse=True)
        return search_results[:top_k]

    def get_document(self, doc_id: str) -> dict | None:
        """Get document details with chunks."""
        doc = DocumentDB.get(doc_id)
        if doc:
            chunks = ChunkDB.get_by_document(doc_id)
            doc["chunks"] = chunks
        return doc

    def list_documents(self) -> list[dict]:
        """List all documents."""
        return DocumentDB.list_all()

    def delete_document(self, doc_id: str):
        """Delete a document and its chunks from database and search index."""
        # Remove chunks from search index
        chunks = ChunkDB.get_by_document(doc_id)
        for chunk in chunks:
            self.search_service.remove_from_index(DOCUMENT_INDEX, chunk["id"])

        # Remove uploaded file
        doc = DocumentDB.get(doc_id)
        if doc:
            file_ext = Path(doc["filename"]).suffix
            file_path = UPLOAD_DIR / f"{doc_id}{file_ext}"
            if file_path.exists():
                os.remove(file_path)

        # Delete from database
        DocumentDB.delete(doc_id)
        logger.info(f"Deleted document {doc_id}")

    def get_stats(self) -> dict:
        """Get document statistics."""
        return DocumentDB.get_stats()

    def process_local_file(self, file_path: str) -> dict:
        """
        Process a local file (for auto-indexing from watch folder).
        Copies the file then processes it like an upload.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path, "rb") as f:
            content = f.read()

        return self.upload_document(path.name, content)
