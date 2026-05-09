"""Sentence-transformers embedding provider (local, default)."""

from __future__ import annotations

from .base import EmbeddingProvider

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class SentenceTransformersProvider(EmbeddingProvider):
    name = "sentence-transformers"
    dimensions = 384

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model)
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts).tolist()
