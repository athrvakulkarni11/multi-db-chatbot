"""
Embedding Service — Uses sentence-transformers for local embeddings
"""
import numpy as np
from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL, EMBEDDING_DIMENSION
import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    _instance = None
    _model = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if EmbeddingService._model is None:
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
            EmbeddingService._model = SentenceTransformer(EMBEDDING_MODEL)
            logger.info("✅ Embedding model loaded")

    @property
    def model(self):
        return EmbeddingService._model

    @property
    def dimension(self):
        return EMBEDDING_DIMENSION

    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text string."""
        embedding = self.model.encode(text, normalize_embeddings=True)
        return np.array(embedding, dtype=np.float32)

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Embed a batch of text strings."""
        if not texts:
            return np.array([], dtype=np.float32)
        embeddings = self.model.encode(texts, normalize_embeddings=True, batch_size=32)
        return np.array(embeddings, dtype=np.float32)

    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        return float(np.dot(embedding1, embedding2))
