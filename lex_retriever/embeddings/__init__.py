"""Embedding provider factory and ChromaDB adapter."""

from __future__ import annotations

import os

from .base import EmbeddingProvider
from .sentence_transformers import DEFAULT_MODEL as _DEFAULT_ST_MODEL


class _ProviderEmbeddingFunction:
    """Adapts an EmbeddingProvider to ChromaDB's EmbeddingFunction interface."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        self._provider = provider

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self._provider.embed(list(input))


def get_embedding_provider(config: dict | None = None) -> EmbeddingProvider:
    """Instantiate the embedding provider specified in config."""
    cfg = config or {}
    provider_name = cfg.get("provider", "sentence-transformers")
    model = cfg.get("model")
    api_key_env = cfg.get("api_key_env")
    api_key = os.environ.get(api_key_env) if api_key_env else None

    if provider_name == "sentence-transformers":
        from .sentence_transformers import SentenceTransformersProvider
        return SentenceTransformersProvider(model=model or _DEFAULT_ST_MODEL)

    if provider_name == "mistral":
        from .mistral import MistralEmbeddingProvider
        kw: dict = {}
        if model:
            kw["model"] = model
        if api_key:
            kw["api_key"] = api_key
        return MistralEmbeddingProvider(**kw)

    if provider_name == "google":
        from .google import GoogleEmbeddingProvider
        kw = {}
        if model:
            kw["model"] = model
        if api_key:
            kw["api_key"] = api_key
        return GoogleEmbeddingProvider(**kw)

    raise ValueError(
        f"Unknown embedding provider: {provider_name!r}. "
        "Choose from: sentence-transformers, mistral, google"
    )


def get_chroma_embedding_function(config: dict | None = None) -> _ProviderEmbeddingFunction:
    """Return a ChromaDB-compatible embedding function for the configured provider."""
    cfg = config or {}
    provider_name = cfg.get("provider", "sentence-transformers")

    if provider_name == "sentence-transformers":
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        model = cfg.get("model", _DEFAULT_ST_MODEL)
        return SentenceTransformerEmbeddingFunction(model_name=model)  # type: ignore[return-value]

    return _ProviderEmbeddingFunction(get_embedding_provider(cfg))


__all__ = ["EmbeddingProvider", "get_embedding_provider", "get_chroma_embedding_function"]
