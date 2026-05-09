"""Google Gemini API embedding provider."""

from __future__ import annotations

from .base import EmbeddingProvider


class GoogleEmbeddingProvider(EmbeddingProvider):
    name = "google"
    dimensions = 768

    def __init__(self, model: str = "text-embedding-004", api_key: str | None = None) -> None:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._genai = genai
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            self._genai.embed_content(
                model=f"models/{self.model}",
                content=text,
                task_type="retrieval_document",
            )["embedding"]
            for text in texts
        ]
