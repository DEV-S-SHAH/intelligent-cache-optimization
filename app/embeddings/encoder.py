"""Embedding encoder with sentence-transformers and fallback options."""

import os
import logging
import hashlib
import math
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingEncoder:
    _instance: Optional["EmbeddingEncoder"] = None

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None
        self._dimension = 384
        self._load_model()

    def _load_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            logger.debug("Loaded sentence-transformers model: %s", self.model_name)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed, using hash-based fallback encoder"
            )
            self._model = None

    def encode(self, text: str) -> List[float]:
        if self._model is not None:
            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        return self._hash_embedding(text)

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        if self._model is not None:
            embeddings = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            return embeddings.tolist()
        return [self._hash_embedding(t) for t in texts]

    def _hash_embedding(self, text: str) -> List[float]:
        words = text.lower().split()
        embedding = [0.0] * self._dimension
        
        for word in words:
            word_hash = int(hashlib.sha256(word.encode()).hexdigest(), 16)
            idx = word_hash % self._dimension
            sign = 1.0 if (word_hash >> 16) % 2 == 0 else -1.0
            embedding[idx] += sign
        
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding

    @classmethod
    def get_instance(cls, model_name: Optional[str] = None) -> "EmbeddingEncoder":
        if cls._instance is None:
            model = model_name or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            cls._instance = cls(model)
        return cls._instance


def get_encoder() -> EmbeddingEncoder:
    """Get the global embedding encoder instance."""
    return EmbeddingEncoder.get_instance()
