"""Mistral API embedding provider."""

from __future__ import annotations

from .base import EmbeddingProvider


class MistralEmbeddingProvider(EmbeddingProvider):
    name = "mistral"
    dimensions = 1024

    def __init__(self, model: str = "mistral-embed", api_key: str | None = None) -> None:
        from mistralai import Mistral
        self.client = Mistral(api_key=api_key)
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(model=self.model, inputs=texts)
        return [r.embedding for r in response.data]
