"""Agent-callable tool wrapper for lex-retriever.

This module provides the primary entry point for agents.
Optionally expose via FastAPI with: uvicorn lex_retriever.tool:app
"""

from .retriever import search as _search


def search_law(query: str, laws: list[str] = None, top_k: int = 10) -> list[dict]:
    """Semantic search over indexed German law paragraphs.

    Args:
        query:  Natural language question or legal term
        laws:   Optional filter e.g. ["BGB", "HGB"] — None = search all
        top_k:  Number of results to return (default 10)

    Returns:
        List of dicts: { "law": str, "paragraph": str, "text": str, "score": float }
    """
    return _search(query=query, laws=laws, top_k=top_k)


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
