"""Mistral API embedding provider."""

from __future__ import annotations

from .base import EmbeddingProvider


class MistralEmbeddingProvider(EmbeddingProvider):
    name = "mistral"
    dimensions = 1024

    def __init__(self, model: str = "mistral-embed", api_key: str | None = None) -> None:
        try:
            from mistralai import Mistral  # mistralai < 2 (has __init__.py)
        except ImportError:
            from mistralai.client import Mistral  # mistralai >= 2 (namespace package)
        self.client = Mistral(api_key=api_key)
        self.model = model

    def embed(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        results: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self.client.embeddings.create(model=self.model, inputs=batch)
            results.extend(r.embedding for r in response.data)
        return results
