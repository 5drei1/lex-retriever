"""Retriever: semantic search over ChromaDB-indexed law paragraphs."""

from __future__ import annotations

import os

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

CHROMA_PATH = os.environ.get("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "..", "chroma_db"))
COLLECTION_NAME = "german_law"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_client: chromadb.PersistentClient | None = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
        ef = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        _collection = _client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)
    return _collection


def search(query: str, laws: list[str] | None = None, top_k: int = 10) -> list[dict]:
    """Semantic search over indexed German law paragraphs.

    Args:
        query:  Natural language question or legal term
        laws:   Optional filter e.g. ["BGB", "HGB"] — None = search all
        top_k:  Number of results to return

    Returns:
        List of dicts: { law, paragraph, text, score }
    """
    collection = _get_collection()

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
