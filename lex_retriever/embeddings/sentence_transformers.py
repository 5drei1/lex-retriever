"""Sentence-transformers embedding provider (local, default)."""

from __future__ import annotations

from .base import EmbeddingProvider

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class SentenceTransformersProvider(EmbeddingProvider):
    name = "sentence-transformers"
    dimensions = 384

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        self._ef = SentenceTransformerEmbeddingFunction(model_name=model)
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return list(self._ef(texts))
