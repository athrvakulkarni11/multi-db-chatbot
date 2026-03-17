"""
Semantic Search Service — FAISS vector store + BM25 hybrid search
"""
import os
import json
import numpy as np
import faiss
from pathlib import Path
from rank_bm25 import BM25Okapi
from services.embedding_service import EmbeddingService
from config import VECTOR_DIR, SEARCH_TOP_K, SIMILARITY_THRESHOLD
import logging

logger = logging.getLogger(__name__)


class VectorIndex:
    """Manages a FAISS index for a specific collection."""

    def __init__(self, name: str, dimension: int):
        self.name = name
        self.dimension = dimension
        self.index_path = VECTOR_DIR / f"{name}.index"
        self.meta_path = VECTOR_DIR / f"{name}.meta.json"
        self.index = None
        self.id_map: list[str] = []  # Maps FAISS internal IDs to our string IDs
        self.text_map: dict[str, str] = {}  # Maps string IDs to original text
        self._load_or_create()

    def _load_or_create(self):
        """Load existing index or create a new one."""
        if self.index_path.exists() and self.meta_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                with open(self.meta_path, "r") as f:
                    meta = json.load(f)
                    self.id_map = meta.get("id_map", [])
                    self.text_map = meta.get("text_map", {})
                logger.info(f"Loaded index '{self.name}' with {self.index.ntotal} vectors")
            except Exception as e:
                logger.error(f"Error loading index '{self.name}': {e}")
                self._create_new()
        else:
            self._create_new()

    def _create_new(self):
        """Create a new FAISS index."""
        self.index = faiss.IndexFlatIP(self.dimension)  # Inner product (cosine sim with normalized vecs)
        self.id_map = []
        self.text_map = {}
        logger.info(f"Created new index '{self.name}'")

    def save(self):
        """Persist index and metadata to disk."""
        faiss.write_index(self.index, str(self.index_path))
        with open(self.meta_path, "w") as f:
            json.dump({"id_map": self.id_map, "text_map": self.text_map}, f)
        logger.info(f"Saved index '{self.name}' ({self.index.ntotal} vectors)")

    def add(self, item_id: str, embedding: np.ndarray, text: str = ""):
        """Add a single vector to the index."""
        if item_id in self.id_map:
            # Remove the old embedding before adding new one
            self.remove(item_id)
        
        vec = embedding.reshape(1, -1).astype(np.float32)
        self.index.add(vec)
        self.id_map.append(item_id)
        if text:
            self.text_map[item_id] = text

    def add_batch(self, item_ids: list[str], embeddings: np.ndarray, texts: list[str] = None):
        """Add a batch of vectors to the index."""
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)
        embeddings = embeddings.astype(np.float32)
        self.index.add(embeddings)
        self.id_map.extend(item_ids)
        if texts:
            for item_id, text in zip(item_ids, texts):
                self.text_map[item_id] = text

    def remove(self, item_id: str):
        """Remove a vector from the index (by rebuilding without it)."""
        if item_id not in self.id_map:
            return
        
        idx = self.id_map.index(item_id)
        
        # Rebuild the index without the removed item
        if self.index.ntotal > 1:
            all_vectors = faiss.rev_swig_ptr(self.index.get_xb(), self.index.ntotal * self.dimension)
            all_vectors = np.array(all_vectors).reshape(-1, self.dimension)
            mask = np.ones(len(all_vectors), dtype=bool)
            mask[idx] = False
            remaining = all_vectors[mask]
            
            self.index = faiss.IndexFlatIP(self.dimension)
            self.index.add(remaining.astype(np.float32))
        else:
            self.index = faiss.IndexFlatIP(self.dimension)
        
        self.id_map.pop(idx)
        self.text_map.pop(item_id, None)

    def search(self, query_embedding: np.ndarray, top_k: int = SEARCH_TOP_K) -> list[dict]:
        """Search the index for similar vectors."""
        if self.index.ntotal == 0:
            return []

        query_vec = query_embedding.reshape(1, -1).astype(np.float32)
        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query_vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.id_map):
                continue
            if score < SIMILARITY_THRESHOLD:
                continue
            item_id = self.id_map[idx]
            results.append({
                "id": item_id,
                "score": float(score),
                "text": self.text_map.get(item_id, "")
            })
        return results

    @property
    def size(self):
        return self.index.ntotal


class SearchService:
    """Hybrid search combining semantic (FAISS) + keyword (BM25) search."""

    def __init__(self):
        self.embedding_service = EmbeddingService.get_instance()
        self.indices: dict[str, VectorIndex] = {}
        self._bm25_corpus: dict[str, list[str]] = {}
        self._bm25_ids: dict[str, list[str]] = {}

    def get_or_create_index(self, name: str) -> VectorIndex:
        """Get or create a named vector index."""
        if name not in self.indices:
            self.indices[name] = VectorIndex(name, self.embedding_service.dimension)
        return self.indices[name]

    def add_to_index(self, index_name: str, item_id: str, text: str):
        """Add a text item to the specified index."""
        index = self.get_or_create_index(index_name)
        embedding = self.embedding_service.embed_text(text)
        index.add(item_id, embedding, text)
        index.save()

        # Update BM25 corpus
        if index_name not in self._bm25_corpus:
            self._bm25_corpus[index_name] = []
            self._bm25_ids[index_name] = []
        self._bm25_corpus[index_name].append(text.lower().split())
        self._bm25_ids[index_name].append(item_id)

    def add_batch_to_index(self, index_name: str, items: list[dict]):
        """Add a batch of items. Each item: {id, text}."""
        if not items:
            return
        index = self.get_or_create_index(index_name)
        texts = [item["text"] for item in items]
        ids = [item["id"] for item in items]
        embeddings = self.embedding_service.embed_texts(texts)
        index.add_batch(ids, embeddings, texts)
        index.save()

        # Update BM25 corpus
        if index_name not in self._bm25_corpus:
            self._bm25_corpus[index_name] = []
            self._bm25_ids[index_name] = []
        for item in items:
            self._bm25_corpus[index_name].append(item["text"].lower().split())
            self._bm25_ids[index_name].append(item["id"])

    def remove_from_index(self, index_name: str, item_id: str):
        """Remove an item from the specified index."""
        if index_name in self.indices:
            self.indices[index_name].remove(item_id)
            self.indices[index_name].save()

            # Update BM25
            if index_name in self._bm25_ids and item_id in self._bm25_ids[index_name]:
                idx = self._bm25_ids[index_name].index(item_id)
                self._bm25_ids[index_name].pop(idx)
                self._bm25_corpus[index_name].pop(idx)

    def semantic_search(self, index_name: str, query: str, top_k: int = SEARCH_TOP_K) -> list[dict]:
        """Perform semantic search using embeddings."""
        index = self.get_or_create_index(index_name)
        query_embedding = self.embedding_service.embed_text(query)
        return index.search(query_embedding, top_k)

    def keyword_search(self, index_name: str, query: str, top_k: int = SEARCH_TOP_K) -> list[dict]:
        """Perform BM25 keyword search."""
        if index_name not in self._bm25_corpus or not self._bm25_corpus[index_name]:
            # Build BM25 corpus from index text_map
            index = self.get_or_create_index(index_name)
            if not index.text_map:
                return []
            self._bm25_corpus[index_name] = [t.lower().split() for t in index.text_map.values()]
            self._bm25_ids[index_name] = list(index.text_map.keys())

        corpus = self._bm25_corpus[index_name]
        ids = self._bm25_ids[index_name]
        if not corpus:
            return []

        bm25 = BM25Okapi(corpus)
        query_tokens = query.lower().split()
        scores = bm25.get_scores(query_tokens)

        # Get top K
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                index = self.get_or_create_index(index_name)
                item_id = ids[idx]
                results.append({
                    "id": item_id,
                    "score": float(scores[idx]),
                    "text": index.text_map.get(item_id, "")
                })
        return results

    def hybrid_search(self, index_name: str, query: str, top_k: int = SEARCH_TOP_K,
                      semantic_weight: float = 0.7) -> list[dict]:
        """Perform hybrid search combining semantic and keyword search."""
        semantic_results = self.semantic_search(index_name, query, top_k * 2)
        keyword_results = self.keyword_search(index_name, query, top_k * 2)

        # Normalize scores
        if semantic_results:
            max_sem = max(r["score"] for r in semantic_results)
            for r in semantic_results:
                r["score"] = r["score"] / max_sem if max_sem > 0 else 0

        if keyword_results:
            max_kw = max(r["score"] for r in keyword_results)
            for r in keyword_results:
                r["score"] = r["score"] / max_kw if max_kw > 0 else 0

        # Merge results using weighted combination
        combined = {}
        for r in semantic_results:
            combined[r["id"]] = {
                "id": r["id"],
                "score": r["score"] * semantic_weight,
                "text": r["text"]
            }

        keyword_weight = 1 - semantic_weight
        for r in keyword_results:
            if r["id"] in combined:
                combined[r["id"]]["score"] += r["score"] * keyword_weight
            else:
                combined[r["id"]] = {
                    "id": r["id"],
                    "score": r["score"] * keyword_weight,
                    "text": r["text"]
                }

        # Sort by combined score and return top K
        results = sorted(combined.values(), key=lambda x: x["score"], reverse=True)[:top_k]
        return results

    def get_index_stats(self) -> dict:
        """Get statistics about all indices."""
        stats = {}
        for name, index in self.indices.items():
            stats[name] = {
                "total_vectors": index.size,
                "dimension": index.dimension
            }
        return stats
