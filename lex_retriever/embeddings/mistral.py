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

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(model=self.model, inputs=texts)
        return [r.embedding for r in response.data]
