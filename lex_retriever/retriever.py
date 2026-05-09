"""Retriever: semantic search over ChromaDB-indexed law paragraphs."""

from __future__ import annotations

import os

import chromadb

from .embeddings import get_chroma_embedding_function
from .query_expansion import expand_query

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
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME, embedding_function=ef, metadata={"hnsw:space": "cosine"}
        )
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
    expanded = expand_query(query)

    where = None
    if laws:
        if len(laws) == 1:
            where = {"law": laws[0]}
        else:
            where = {"law": {"$in": list(laws)}}

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
            "score": round(1.0 - (distances[i] / 2), 4),
            "original_query": query,
        }
        for i in range(len(docs))
    ]


def get_paragraph(law: str, paragraph: str, embedding_config: dict | None = None) -> dict | None:
    """Retrieve all chunks of a specific paragraph by exact match.

    Args:
        law:       Law code e.g. "BGB"
        paragraph: Paragraph identifier e.g. "§ 242" or "Art. 20"

    Returns:
        { "law", "paragraph", "text": "<full reconstructed text>", "chunks": int }
        or None if not found
    """
    from collections import defaultdict

    collection = _get_collection(embedding_config)
    result = collection.get(
        where={"law": law.upper()},
        include=["documents", "metadatas"],
    )
    if not result["ids"]:
        return None

    pairs = [
        (meta, doc)
        for meta, doc in zip(result["metadatas"], result["documents"])
        if meta.get("paragraph", "").startswith(paragraph)
    ]
    if not pairs:
        return None

    pairs.sort(key=lambda x: x[0].get("paragraph", ""))
    full_text = " ".join(doc for _, doc in pairs)
    return {
        "law": law.upper(),
        "paragraph": paragraph,
        "text": full_text,
        "chunks": len(pairs),
    }


def get_full_law(law: str, offset: int = 0, limit: int = 50, embedding_config: dict | None = None) -> dict:
    """Return paginated paragraphs of a complete law.

    Args:
        law:    Law code e.g. "AGG"
        offset: Paragraph offset for pagination
        limit:  Number of paragraphs per page (default 50)

    Returns:
        {
          "law": str,
          "total_paragraphs": int,
          "offset": int,
          "paragraphs": [{ "paragraph": str, "text": str }]
        }
    """
    from collections import defaultdict

    collection = _get_collection(embedding_config)
    result = collection.get(
        where={"law": law},
        include=["documents", "metadatas"],
    )

    paragraph_chunks: dict[str, list[tuple[dict, str]]] = defaultdict(list)
    for meta, doc in zip(result["metadatas"], result["documents"]):
        paragraph_chunks[meta["paragraph"]].append((meta, doc))

    sorted_paragraphs = sorted(paragraph_chunks.keys())
    total = len(sorted_paragraphs)
    page = sorted_paragraphs[offset : offset + limit]

    paragraphs = []
    for para_key in page:
        chunks = sorted(paragraph_chunks[para_key], key=lambda x: x[0].get("paragraph", ""))
        text = " ".join(doc for _, doc in chunks)
        paragraphs.append({"paragraph": para_key, "text": text})

    return {
        "law": law,
        "total_paragraphs": total,
        "offset": offset,
        "paragraphs": paragraphs,
    }
