"""
Documents Router — API endpoints for document management
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from models.schemas import DocumentOut, DocumentSearchRequest
from services.document_service import DocumentService

router = APIRouter(prefix="/api/documents", tags=["Documents"])

document_service: DocumentService = None


def init_router(service: DocumentService):
    global document_service
    document_service = service


@router.get("/")
async def list_documents():
    """List all uploaded documents."""
    if not document_service:
        raise HTTPException(status_code=500, detail="Document service not initialized")
    return document_service.list_documents()


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and index a document."""
    if not document_service:
        raise HTTPException(status_code=500, detail="Document service not initialized")

    # Validate file type
    allowed_extensions = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv"}
    file_ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
        )

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB.")

    result = document_service.upload_document(file.filename, content)
    return result


@router.get("/{document_id}")
async def get_document(document_id: str):
    """Get document details with chunks."""
    if not document_service:
        raise HTTPException(status_code=500, detail="Document service not initialized")
    doc = document_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document."""
    if not document_service:
        raise HTTPException(status_code=500, detail="Document service not initialized")
    document_service.delete_document(document_id)
    return {"status": "deleted"}


@router.post("/search")
async def search_documents(request: DocumentSearchRequest):
    """Search across indexed documents."""
    if not document_service:
        raise HTTPException(status_code=500, detail="Document service not initialized")
    return document_service.search_documents(
        query=request.query,
        top_k=request.top_k,
        document_ids=request.document_ids
    )


@router.get("/stats/overview")
async def document_stats():
    """Get document statistics."""
    if not document_service:
        raise HTTPException(status_code=500, detail="Document service not initialized")
    return document_service.get_stats()
