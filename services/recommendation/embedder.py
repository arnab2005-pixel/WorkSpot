"""
Vector embedding service generating 768-dim dense embeddings.
Uses BAAI/bge-m3 or Indic-BERT with deterministic fallback for local testing.
"""

import logging

import numpy as np

from config.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CourseEmbedder:
    """
    Generates 768-dimensional dense semantic embeddings for vocational courses and queries.
    """

    def __init__(self, model_name: str | None = None, dim: int = 768):
        self.model_name = model_name or settings.embedding_model
        self.dim = dim
        self._model = None
        self._load_model()

    def _load_model(self):
        """Lazy load sentence-transformers / huggingface model with fallback."""
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded successfully.")
        except Exception as e:  # noqa: BLE001 - embedding failure must use deterministic fallback
            logger.warning(
                "SentenceTransformer not available (%s). "
                "Using deterministic pseudo-embedder for testing.",
                exc,
            )
            self._model = None

    def embed_text(self, text: str) -> list[float]:
        """
        Embed a single text string into a 768-dim normalized vector.
        """
        if not text:
            return [0.0] * self.dim

        if self._model is not None:
            try:
                embedding = self._model.encode(text, normalize_embeddings=True)
                vec = embedding.tolist()
                # Ensure exactly self.dim dimensions
                if len(vec) == self.dim:
                    return vec
                elif len(vec) > self.dim:
                    return vec[: self.dim]
                else:
                    return vec + [0.0] * (self.dim - len(vec))
            except Exception as e:  # noqa: BLE001 - embedding failure must use deterministic fallback
                logger.warning(
                    f"Model embedding failed: {e}. Falling back to pseudo-embedder."
                )

        # Deterministic pseudo-embedding based on text hash for testing
        import hashlib

        h = hashlib.sha256(text.encode("utf-8")).digest()
        rng = np.random.RandomState(int.from_bytes(h[:4], "little"))
        vec = rng.randn(self.dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text strings."""
        return [self.embed_text(t) for t in texts]
