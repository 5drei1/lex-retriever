"""Retriever: semantic search over ChromaDB-indexed law paragraphs."""

from __future__ import annotations

import os

import chromadb

from .embeddings import get_chroma_embedding_function

CHROMA_PATH = os.environ.get("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "..", "chroma_db"))
COLLECTION_NAME = "german_law"

_client: chromadb.PersistentClient | None = None
_collection = None
_collection_config_key: str | None = None


def _get_collection(embedding_config: dict | None = None):
    global _client, _collection, _collection_config_key
    key = str(sorted((embedding_config or {}).items()))
    if _collection is None or _collection_config_key != key:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
        ef = get_chroma_embedding_function(embedding_config)
        _collection = _client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)
        _collection_config_key = key
    return _collection


def search(
    query: str,
    laws: list[str] | None = None,
    top_k: int = 10,
    embedding_config: dict | None = None,
) -> list[dict]:
    """Semantic search over indexed German law paragraphs.

    Args:
        query:            Natural language question or legal term
        laws:             Optional filter e.g. ["BGB", "HGB"] — None = search all
        top_k:            Number of results to return
        embedding_config: Optional embedding section from lex_retriever.toml

    Returns:
        List of dicts: { law, paragraph, text, score }
    """
    collection = _get_collection(embedding_config)

    where = None
    if laws:
        normalized = [l.upper() for l in laws]
        if len(normalized) == 1:
            where = {"law": normalized[0]}
        else:
            where = {"law": {"$in": normalized}}

    kwargs = {
        "query_texts": [query],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    return [
        {
            "law": metas[i]["law"],
            "paragraph": metas[i]["paragraph"],
            "text": docs[i],
            "score": round(1.0 - distances[i], 4),
        }
        for i in range(len(docs))
    ]
