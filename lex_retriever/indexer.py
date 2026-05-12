"""Indexer: fetch law chunks from providers and store in LanceDB."""

from __future__ import annotations

import hashlib
import logging
import os
import re

import lancedb

from .embeddings import get_embedding_provider
from .providers import get_providers_for_law

logger = logging.getLogger(__name__)

LANCE_PATH = os.environ.get("LANCE_PATH", os.path.join(os.path.dirname(__file__), "..", "lancedb"))
TABLE_NAME = "german_law"
_CHUNK_MAX_WORDS = 100
_CHUNK_OVERLAP_WORDS = 20
_WS_RE = re.compile(r"\s+")


def _normalize_paragraph(paragraph: str) -> str:
    """Collapse internal whitespace so paragraph keys are stable."""
    return _WS_RE.sub(" ", paragraph).strip()


def _chunk_id(law_code: str, paragraph: str, idx: int) -> str:
    raw = f"{law_code.upper()}|{paragraph}|{idx}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def chunk_text(text: str, max_tokens: int = _CHUNK_MAX_WORDS, overlap: int = _CHUNK_OVERLAP_WORDS) -> list[str]:
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


def _open_table():
    """Open the LanceDB table if it exists, otherwise return None."""
    db = lancedb.connect(LANCE_PATH)
    if TABLE_NAME in db.table_names():
        return db.open_table(TABLE_NAME)
    return None


def index_law(law_code: str, force: bool = False, embedding_config: dict | None = None) -> int:
    providers = get_providers_for_law(law_code)
    if not providers:
        raise ValueError(f"No provider found for law '{law_code}'")

    embedder = get_embedding_provider(embedding_config)
    table = _open_table()

    if table is not None and not force:
        existing = table.search().where(f"law = '{law_code.upper()}'").limit(1).to_list()
        if existing:
            return 0

    if table is not None:
        try:
            table.delete(f"law = '{law_code.upper()}'")
        except Exception:
            pass

    raw_chunks: list[dict] = []
    for provider in providers:
        try:
            raw_chunks.extend(provider.fetch(law_code))
        except Exception as exc:
            logger.warning("Provider %s failed for %s: %s", provider.name, law_code, exc)

    if not raw_chunks:
        return 0

    indexed_chunks = []
    for chunk in raw_chunks:
        # Use chunk text only for embedding — text is NOT stored in LanceDB.
        # ref_id stores the ELI/CELEX/source identifier for on-demand text retrieval.
        sub_chunks = chunk_text(chunk["text"])
        base_paragraph = _normalize_paragraph(chunk["paragraph"])
        for idx, sub_text in enumerate(sub_chunks):
            paragraph = (
                base_paragraph if len(sub_chunks) == 1
                else f"{base_paragraph} [{idx + 1}/{len(sub_chunks)}]"
            )
            indexed_chunks.append({
                "id":        _chunk_id(law_code, paragraph, idx),
                "law":       law_code.upper(),
                "paragraph": paragraph,
                "ref_id":    chunk["source"],   # ELI / CELEX / source identifier
                "_embed_text": sub_text,         # temporary — used for embedding only
            })

    texts = [c.pop("_embed_text") for c in indexed_chunks]
    vectors = embedder.embed(texts)

    rows = [{**chunk, "vector": vector} for chunk, vector in zip(indexed_chunks, vectors)]

    db = lancedb.connect(LANCE_PATH)
    os.makedirs(LANCE_PATH, exist_ok=True)
    batch_size = 32

    if table is None:
        # Re-check table existence against the fresh DB handle to avoid races or
        # stale state between the earlier _open_table() and write phase.
        if TABLE_NAME in db.table_names():
            table = db.open_table(TABLE_NAME)
            for start in range(0, len(rows), batch_size):
                table.add(rows[start:start + batch_size])
        else:
            table = db.create_table(TABLE_NAME, data=rows[:batch_size])
            for start in range(batch_size, len(rows), batch_size):
                table.add(rows[start:start + batch_size])
    else:
        for start in range(0, len(rows), batch_size):
            table.add(rows[start:start + batch_size])

    return len(indexed_chunks)


def index_all_laws(
    force: bool = False,
    law_codes: list[str] | None = None,
    embedding_config: dict | None = None,
) -> dict[str, int]:
    if law_codes is None:
        from .providers import all_supported_laws
        law_codes = all_supported_laws()
    results = {}
    for law_code in law_codes:
        results[law_code] = index_law(law_code, force=force, embedding_config=embedding_config)
    return results


def get_indexed_law_counts() -> dict[str, int]:
    try:
        db = lancedb.connect(LANCE_PATH)
        if TABLE_NAME not in db.table_names():
            return {}
        df = db.open_table(TABLE_NAME).to_pandas()[["law"]]
        return df["law"].value_counts().to_dict()
    except Exception:
        return {}
