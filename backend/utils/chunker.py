"""
Text Chunking Utilities — Smart text splitting strategies
"""
import re
from config import CHUNK_SIZE, CHUNK_OVERLAP


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP,
               strategy: str = "paragraph") -> list[dict]:
    """
    Split text into chunks using the specified strategy.
    
    Returns list of dicts: [{content, start_char, end_char, chunk_index}]
    """
    if strategy == "paragraph":
        return _chunk_by_paragraph(text, chunk_size, chunk_overlap)
    elif strategy == "sentence":
        return _chunk_by_sentence(text, chunk_size, chunk_overlap)
    else:
        return _chunk_by_size(text, chunk_size, chunk_overlap)


def _chunk_by_paragraph(text: str, chunk_size: int, chunk_overlap: int) -> list[dict]:
    """Split text by paragraphs, merging small paragraphs together."""
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_chunk = ""
    current_start = 0
    chunk_index = 0

    for para in paragraphs:
        if len(current_chunk) + len(para) + 1 > chunk_size and current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "start_char": current_start,
                "end_char": current_start + len(current_chunk),
                "chunk_index": chunk_index
            })
            chunk_index += 1

            # Overlap - keep last part of current chunk
            if chunk_overlap > 0:
                overlap_text = current_chunk[-chunk_overlap:]
                current_start = current_start + len(current_chunk) - chunk_overlap
                current_chunk = overlap_text + "\n\n" + para
            else:
                current_start = current_start + len(current_chunk)
                current_chunk = para
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para

    # Add the last chunk
    if current_chunk.strip():
        chunks.append({
            "content": current_chunk.strip(),
            "start_char": current_start,
            "end_char": current_start + len(current_chunk),
            "chunk_index": chunk_index
        })

    return chunks


def _chunk_by_sentence(text: str, chunk_size: int, chunk_overlap: int) -> list[dict]:
    """Split text by sentences."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = ""
    current_start = 0
    chunk_index = 0

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 > chunk_size and current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "start_char": current_start,
                "end_char": current_start + len(current_chunk),
                "chunk_index": chunk_index
            })
            chunk_index += 1

            if chunk_overlap > 0:
                overlap_text = current_chunk[-chunk_overlap:]
                current_start += len(current_chunk) - chunk_overlap
                current_chunk = overlap_text + " " + sentence
            else:
                current_start += len(current_chunk)
                current_chunk = sentence
        else:
            current_chunk = (current_chunk + " " + sentence).strip()

    if current_chunk.strip():
        chunks.append({
            "content": current_chunk.strip(),
            "start_char": current_start,
            "end_char": current_start + len(current_chunk),
            "chunk_index": chunk_index
        })

    return chunks


def _chunk_by_size(text: str, chunk_size: int, chunk_overlap: int) -> list[dict]:
    """Simple fixed-size chunking with overlap."""
    chunks = []
    start = 0
    chunk_index = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_text = text[start:end]
        
        chunks.append({
            "content": chunk_text.strip(),
            "start_char": start,
            "end_char": end,
            "chunk_index": chunk_index
        })
        chunk_index += 1
        start += chunk_size - chunk_overlap

    return chunks
