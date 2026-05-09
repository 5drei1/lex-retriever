"""Agent-callable tool wrapper for lex-retriever.

This module provides the primary entry point for agents.
Optionally expose via FastAPI with: uvicorn lex_retriever.tool:app
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from .retriever import search as _search


def _load_embedding_config() -> dict:
    config_path = Path(os.environ.get("LEX_CONFIG", "lex_retriever.toml"))
    if config_path.exists():
        with open(config_path, "rb") as f:
            cfg = tomllib.load(f)
        return cfg.get("embedding", {}) or {}
    return {}


def search_law(query: str, laws: list[str] = None, top_k: int = 10) -> list[dict]:
    """Semantic search over indexed German law paragraphs.

    Args:
        query:  Natural language question or legal term
        laws:   Optional filter e.g. ["BGB", "HGB"] — None = search all
        top_k:  Number of results to return (default 10)

    Returns:
        List of dicts: { "law": str, "paragraph": str, "text": str, "score": float }
    """
    embedding_config = _load_embedding_config()
    return _search(query=query, laws=laws, top_k=top_k, embedding_config=embedding_config or None)


try:
    from fastapi import FastAPI
    from pydantic import BaseModel

    app = FastAPI(title="lex-retriever", description="Semantic search over German law")

    class SearchRequest(BaseModel):
        query: str
        laws: list[str] | None = None
        top_k: int = 10

    @app.post("/search")
    def http_search(req: SearchRequest) -> list[dict]:
        return search_law(query=req.query, laws=req.laws, top_k=req.top_k)

    @app.get("/health")
    def health():
        return {"status": "ok"}

except ImportError:
    app = None
