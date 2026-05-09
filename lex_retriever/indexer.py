"""Indexer: fetch law chunks from providers and store in ChromaDB."""

from __future__ import annotations

import os

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from .providers import get_providers_for_law

CHROMA_PATH = os.environ.get("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "..", "chroma_db"))
COLLECTION_NAME = "german_law"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    return client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)


def index_law(law_code: str, force: bool = False) -> int:
    """Fetch and index all paragraphs for a given law code.

    Args:
        law_code: Law abbreviation e.g. "BGB"
        force:    Re-index even if already present

    Returns:
        Number of paragraphs indexed
    """
    providers = get_providers_for_law(law_code)
    if not providers:
        raise ValueError(f"No provider found for law '{law_code}'")

    collection = _get_collection()

    # Check existing entries if not forcing
    if not force:
        existing = collection.get(where={"law": law_code.upper()}, limit=1)
        if existing["ids"]:
            return 0

    chunks = []
    for provider in providers:
        chunks.extend(provider.fetch(law_code))

    if not chunks:
        return 0

    ids = [f"{law_code.upper()}_{i}" for i in range(len(chunks))]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "law": law_code.upper(),
            "paragraph": c["paragraph"],
            "source": c["source"],
        }
        for c in chunks
    ]

    # Delete stale entries before upserting (handles force re-index)
    if force:
        existing_ids = collection.get(where={"law": law_code.upper()})["ids"]
        if existing_ids:
            collection.delete(ids=existing_ids)

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(chunks)


def index_all_laws(force: bool = False, law_codes: list[str] | None = None) -> dict[str, int]:
    """Index laws from all registered providers.

    Args:
        force:      Re-index even if laws are already present
        law_codes:  Explicit list of law codes to index; defaults to all supported laws

    Returns:
        Dict mapping law code to number of chunks indexed (0 = already up to date)
    """
    if law_codes is None:
        from .providers import all_supported_laws
        law_codes = all_supported_laws()
    results = {}
    for law_code in law_codes:
        results[law_code] = index_law(law_code, force=force)
    return results


def get_indexed_law_counts() -> dict[str, int]:
    """Return {law_code: chunk_count} for every law currently in the DB."""
    try:
        collection = _get_collection()
        result = collection.get(include=["metadatas"])
        counts: dict[str, int] = {}
        for meta in result["metadatas"]:
            law = meta.get("law", "UNKNOWN")
            counts[law] = counts.get(law, 0) + 1
        return counts
    except Exception:
        return {}
