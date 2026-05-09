"""Retriever: semantic search over ChromaDB-indexed law paragraphs."""

from __future__ import annotations

import os

import chromadb

from .embeddings import get_chroma_embedding_function
from .query_expansion import expand_query

CHROMA_PATH = os.environ.get("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "..", "chroma_db"))
COLLECTION_NAME = "german_law"


class LexRetriever:
    def __init__(self, chroma_path: str = CHROMA_PATH, embedding_config: dict | None = None):
        self._chroma_path = chroma_path
        self._embedding_config = embedding_config
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            client = chromadb.PersistentClient(path=self._chroma_path)
            ef = get_chroma_embedding_function(self._embedding_config)
            self._collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def search(self, query: str, laws: list[str] | None = None, top_k: int = 10) -> list[dict]:
        """Semantic search over indexed German law paragraphs.

        Args:
            query:   Natural language question or legal term
            laws:    Optional filter e.g. ["BGB", "HGB"] — None = search all
            top_k:   Number of results to return

        Returns:
            List of dicts: { law, paragraph, text, score }
        """
        collection = self._get_collection()
        expanded = expand_query(query)

        where = None
        if laws:
            normalized = [law.upper() for law in laws]
            if len(normalized) == 1:
                where = {"law": normalized[0]}
            else:
                where = {"law": {"$in": normalized}}

        kwargs = {
            "query_texts": [expanded],
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
                "original_query": query,
            }
            for i in range(len(docs))
        ]


def search(
    query: str,
    laws: list[str] | None = None,
    top_k: int = 10,
    embedding_config: dict | None = None,
) -> list[dict]:
    """Backwards-compatible module-level search wrapper."""
    return LexRetriever(embedding_config=embedding_config).search(query, laws, top_k)
