"""Retriever: semantic search over LanceDB-indexed law paragraphs.

LanceDB stores only embeddings + ref_id (no full text). After a vector
search returns candidate chunks, text is fetched on-demand from the
appropriate provider using the law abbreviation stored in `law`.
"""

from __future__ import annotations

import os
import re
from typing import Any

# Matches chunked paragraph keys produced by the indexer: "§ 123 [1/2]"
_CHUNK_RE = re.compile(r"^(.*)\s+\[(\d+)/(\d+)\]$")
_WS_RE = re.compile(r"\s+")

import lancedb

from .embeddings import get_embedding_provider
from .providers import get_providers_for_law
from .query_expansion import expand_query

LANCE_PATH = os.environ.get("LANCE_PATH", os.path.join(os.path.dirname(__file__), "..", "lancedb"))
TABLE_NAME = "german_law"


def _fetch_law_chunks(law_code: str) -> list[dict]:
    """Return all raw chunks for a law from the first available provider."""
    providers = get_providers_for_law(law_code)
    for provider in providers:
        try:
            return provider.fetch(law_code)
        except Exception:
            continue
    return []


def _build_text_index(law_code: str) -> dict[str, str]:
    """Map paragraph key → text for all chunks of a law."""
    index: dict[str, str] = {}
    for chunk in _fetch_law_chunks(law_code):
        key = _WS_RE.sub(" ", chunk["paragraph"]).strip()
        index[key] = chunk["text"]
    return index


def _resolve_ref_id(row: dict[str, Any]) -> str:
    """Resolve source identifier from row-level or metadata fields."""
    direct = row.get("ref_id") or row.get("source")
    if direct:
        return str(direct)
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        meta_source = metadata.get("source") or metadata.get("ref_id")
        if meta_source:
            return str(meta_source)
    return ""


class LexRetriever:
    def __init__(self, lance_path: str = LANCE_PATH, embedding_config: dict | None = None):
        self._lance_path = lance_path
        self._embedding_config = embedding_config
        self._table = None
        self._embedder = get_embedding_provider(embedding_config)
        # Per-instance cache: law_code → {paragraph: text}
        self._text_cache: dict[str, dict[str, str]] = {}

    def _get_table(self):
        if self._table is None:
            db = lancedb.connect(self._lance_path)
            self._table = db.open_table(TABLE_NAME)
        return self._table

    def _get_text(self, law_code: str, paragraph: str) -> str:
        """Return the text for a specific paragraph, fetching from provider if needed."""
        if law_code not in self._text_cache:
            self._text_cache[law_code] = _build_text_index(law_code)
        cache = self._text_cache[law_code]
        normalized_paragraph = _WS_RE.sub(" ", paragraph).strip()
        text = cache.get(normalized_paragraph, "")
        if not text:
            # Backward-compatible fallback for already-populated caches that used
            # unnormalized keys (e.g. keys containing newlines).
            normalized_cache = {_WS_RE.sub(" ", k).strip(): v for k, v in cache.items()}
            if normalized_cache != cache:
                self._text_cache[law_code] = normalized_cache
                cache = normalized_cache
            text = cache.get(normalized_paragraph, "")
        if text:
            return text
        # Providers return base keys (e.g. "§ 123") but the indexer stores chunked
        # keys (e.g. "§ 123 [1/2]"). Re-apply the same chunking to find the sub-chunk.
        m = _CHUNK_RE.match(normalized_paragraph)
        if m:
            base, chunk_idx = m.group(1), int(m.group(2)) - 1
            base_text = cache.get(base, "")
            if base_text:
                from .indexer import chunk_text
                sub_chunks = chunk_text(base_text)
                if 0 <= chunk_idx < len(sub_chunks):
                    return sub_chunks[chunk_idx]
        return ""

    def search(self, query: str, laws: list[str] | None = None, top_k: int = 10) -> list[dict]:
        table = self._get_table()
        expanded = expand_query(query)
        vector = self._embedder.embed([expanded])

        q = table.search(vector, vector_column_name="vector")

        if laws:
            normalized = [l.upper() for l in laws]
            if len(normalized) == 1:
                q = q.where(f"law = '{normalized[0]}'")
            else:
                in_clause = ", ".join(f"'{l}'" for l in normalized)
                q = q.where(f"law IN ({in_clause})")

        results = q.limit(top_k).to_list()

        output = []
        for r in results:
            law = r["law"]
            paragraph = r["paragraph"]
            text = self._get_text(law, paragraph)
            ref_id = _resolve_ref_id(r)
            output.append({
                "law":            law,
                "paragraph":      paragraph,
                "text":           text,
                "ref_id":         ref_id,
                "source":         ref_id,
                "score":          round(1.0 - (r["_distance"] / 2), 4),
                "original_query": query,
            })
        return output

    def get_paragraph(self, law: str, paragraph: str) -> dict | None:
        table = self._get_table()
        results = (
            table.search()
            .where(f"law = '{law.upper()}' AND paragraph LIKE '%{paragraph}%'")
            .to_list()
        )
        if not results:
            return None
        results.sort(key=lambda r: r["paragraph"])
        # Fetch and combine text for all matching chunks on-demand
        texts = [self._get_text(law.upper(), r["paragraph"]) for r in results]
        full_text = " ".join(t for t in texts if t)
        return {"law": law.upper(), "paragraph": paragraph, "text": full_text, "chunks": len(results)}

    def get_full_law(self, law: str, offset: int = 0, limit: int = 50) -> dict:
        from collections import defaultdict

        table = self._get_table()
        results = (
            table.search()
            .where(f"law = '{law.upper()}'")
            .to_list()
        )

        paragraph_chunks: dict[str, list[Any]] = defaultdict(list)
        for row in results:
            paragraph_chunks[row["paragraph"]].append(row)

        sorted_paragraphs = sorted(paragraph_chunks.keys())
        total = len(sorted_paragraphs)
        page = sorted_paragraphs[offset:offset + limit]

        paragraphs = []
        for para_key in page:
            text = self._get_text(law.upper(), para_key)
            paragraphs.append({"paragraph": para_key, "text": text})

        return {
            "law": law.upper(),
            "total_paragraphs": total,
            "offset": offset,
            "paragraphs": paragraphs,
        }


# Backwards-compat wrappers
def search(query: str, laws: list[str] | None = None, top_k: int = 10,
           embedding_config: dict | None = None) -> list[dict]:
    return LexRetriever(embedding_config=embedding_config).search(query, laws, top_k)


def get_paragraph(law: str, paragraph: str, embedding_config: dict | None = None) -> dict | None:
    return LexRetriever(embedding_config=embedding_config).get_paragraph(law, paragraph)


def get_full_law(law: str, offset: int = 0, limit: int = 50,
                 embedding_config: dict | None = None) -> dict:
    return LexRetriever(embedding_config=embedding_config).get_full_law(law, offset, limit)
