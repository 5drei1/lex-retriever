"""Indexer: fetch law chunks from providers and store in ChromaDB."""

from __future__ import annotations

import logging
import os

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from .providers import get_providers_for_law

logger = logging.getLogger(__name__)

CHROMA_PATH = os.environ.get("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "..", "chroma_db"))
COLLECTION_NAME = "german_law"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# Model hard limit is 128 tokens; 100-word chunks stay safely under it (German ~1.3 tokens/word).
_CHUNK_MAX_WORDS = 100
_CHUNK_OVERLAP_WORDS = 20


def chunk_text(text: str, max_tokens: int = _CHUNK_MAX_WORDS, overlap: int = _CHUNK_OVERLAP_WORDS) -> list[str]:
    """Split text into overlapping word-level chunks within the token limit.

    Uses word-level splitting as an approximation (1 word ≈ 1.3 tokens for German).
    max_tokens=100 gives a safe margin below the 128-token model hard limit.
    overlap=20 preserves context continuity across chunk boundaries.
    """
    words = text.split()
    if len(words) <= max_tokens:
        return [text]
    chunks: list[str] = []
    step = max_tokens - overlap
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + max_tokens])
        if chunk:
            chunks.append(chunk)
    return chunks


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
        Number of chunks indexed (0 = already up to date)
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

    raw_chunks: list[dict] = []
    for provider in providers:
        raw_chunks.extend(provider.fetch(law_code))

    if not raw_chunks:
        return 0

    # Split long paragraphs into overlapping sub-chunks so nothing exceeds the
    # 128-token model limit. Short paragraphs pass through as-is.
    indexed_chunks: list[dict] = []
    for chunk in raw_chunks:
        sub_chunks = chunk_text(chunk["text"])
        if len(sub_chunks) > 1:
            logger.warning(
                "%s %s: split into %d chunks (text too long for 128-token model limit)",
                law_code,
                chunk["paragraph"],
                len(sub_chunks),
            )
        for idx, sub_text in enumerate(sub_chunks):
            indexed_chunks.append(
                {
                    "paragraph": chunk["paragraph"]
                    if len(sub_chunks) == 1
                    else f"{chunk['paragraph']} [{idx + 1}/{len(sub_chunks)}]",
                    "text": sub_text,
                    "source": chunk["source"],
                }
            )

    ids = [f"{law_code.upper()}_{i}" for i in range(len(indexed_chunks))]
    documents = [c["text"] for c in indexed_chunks]
    metadatas = [
        {
            "law": law_code.upper(),
            "paragraph": c["paragraph"],
            "source": c["source"],
        }
        for c in indexed_chunks
    ]

    # Delete stale entries before upserting (handles force re-index)
    if force:
        existing_ids = collection.get(where={"law": law_code.upper()})["ids"]
        if existing_ids:
            collection.delete(ids=existing_ids)

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(indexed_chunks)


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
