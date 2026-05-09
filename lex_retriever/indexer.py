"""Indexer: fetch law chunks from providers and store in ChromaDB."""

from __future__ import annotations

import json
import logging
import os

import chromadb

from .embeddings import get_chroma_embedding_function
from .providers import get_providers_for_law

logger = logging.getLogger(__name__)

CHROMA_PATH = os.environ.get("CHROMA_PATH", os.path.join(os.path.dirname(__file__), "..", "chroma_db"))
COLLECTION_NAME = "german_law"
_CHUNK_MAX_WORDS = 100
_CHUNK_OVERLAP_WORDS = 20

_PROVIDER_FILE = ".embedding_provider"


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


def _provider_id(embedding_config: dict | None) -> str:
    cfg = embedding_config or {}
    provider = cfg.get("provider", "sentence-transformers")
    model = cfg.get("model", "")
    return f"{provider}:{model}" if model else provider


def _provider_file_path() -> str:
    return os.path.join(CHROMA_PATH, _PROVIDER_FILE)


def _read_stored_provider() -> str | None:
    path = _provider_file_path()
    try:
        with open(path) as f:
            return json.load(f).get("provider_id")
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def _write_stored_provider(provider_id: str) -> None:
    os.makedirs(CHROMA_PATH, exist_ok=True)
    with open(_provider_file_path(), "w") as f:
        json.dump({"provider_id": provider_id}, f)


def _get_collection(embedding_config: dict | None = None, force: bool = False):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = get_chroma_embedding_function(embedding_config)
    collection_metadata = {"hnsw:space": "cosine"}
    try:
        return client.get_or_create_collection(
            name=COLLECTION_NAME, embedding_function=ef, metadata=collection_metadata
        )
    except ValueError as exc:
        if "Embedding function conflict" in str(exc) and force:
            # Provider changed with --force: drop the whole collection and start fresh.
            client.delete_collection(name=COLLECTION_NAME)
            return client.get_or_create_collection(
                name=COLLECTION_NAME, embedding_function=ef, metadata=collection_metadata
            )
        raise


def _check_provider_change(embedding_config: dict | None, force: bool) -> None:
    stored = _read_stored_provider()
    current = _provider_id(embedding_config)
    if stored and stored != current:
        import sys
        print(
            f"Warning: embedding provider changed from '{stored}' to '{current}'. "
            "The existing index was built with a different provider — search results will be unreliable. "
            "Re-index with --force to rebuild the index with the new provider.",
            file=sys.stderr,
        )


def index_law(law_code: str, force: bool = False, embedding_config: dict | None = None) -> int:
    """Fetch and index all paragraphs for a given law code.

    Args:
        law_code:         Law abbreviation e.g. "BGB"
        force:            Re-index even if already present
        embedding_config: Optional embedding section from lex_retriever.toml

    Returns:
        Number of chunks indexed (0 = already up to date)
    """
    providers = get_providers_for_law(law_code)
    if not providers:
        raise ValueError(f"No provider found for law '{law_code}'")

    _check_provider_change(embedding_config, force)
    collection = _get_collection(embedding_config, force=force)

    if not force:
        existing = collection.get(where={"law": law_code.upper()}, limit=1)
        if existing["ids"]:
            return 0

    raw_chunks: list[dict] = []
    for provider in providers:
        raw_chunks.extend(provider.fetch(law_code))

    if not raw_chunks:
        return 0

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

    if force:
        existing_ids = collection.get(where={"law": law_code.upper()})["ids"]
        if existing_ids:
            collection.delete(ids=existing_ids)

    batch_size = 32
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        collection.add(
            ids=ids[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )
    _write_stored_provider(_provider_id(embedding_config))
    return len(indexed_chunks)


def index_all_laws(
    force: bool = False,
    law_codes: list[str] | None = None,
    embedding_config: dict | None = None,
) -> dict[str, int]:
    """Index laws from all registered providers.

    Args:
        force:            Re-index even if laws are already present
        law_codes:        Explicit list of law codes to index; defaults to all supported laws
        embedding_config: Optional embedding section from lex_retriever.toml

    Returns:
        Dict mapping law code to number of chunks indexed (0 = already up to date)
    """
    if law_codes is None:
        from .providers import all_supported_laws
        law_codes = all_supported_laws()
    results = {}
    for law_code in law_codes:
        results[law_code] = index_law(law_code, force=force, embedding_config=embedding_config)
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
