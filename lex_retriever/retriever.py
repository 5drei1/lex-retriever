"""Retriever: semantic search over LanceDB-indexed law paragraphs."""

from __future__ import annotations

import os
import lancedb

from .embeddings import get_embedding_provider
from .query_expansion import expand_query

LANCE_PATH = os.environ.get("LANCE_PATH", os.path.join(os.path.dirname(__file__), "..", "lancedb"))
TABLE_NAME = "german_law"


class LexRetriever:
    def __init__(self, lance_path: str = LANCE_PATH, embedding_config: dict | None = None):
        self._lance_path = lance_path
        self._embedding_config = embedding_config
        self._table = None
        self._embedder = get_embedding_provider(embedding_config)

    def _get_table(self):
        if self._table is None:
            db = lancedb.connect(self._lance_path)
            self._table = db.open_table(TABLE_NAME)
        return self._table

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

        return [
            {
                "law":            r["law"],
                "paragraph":      r["paragraph"],
                "text":           r["text"],
                "score":          round(1.0 - (r["_distance"] / 2), 4),
                "original_query": query,
            }
            for r in results
        ]

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
        full_text = " ".join(r["text"] for r in results)
        return {"law": law.upper(), "paragraph": paragraph, "text": full_text, "chunks": len(results)}

    def get_full_law(self, law: str, offset: int = 0, limit: int = 50) -> dict:
        from collections import defaultdict

        table = self._get_table()
        results = (
            table.search()
            .where(f"law = '{law.upper()}'")
            .to_list()
        )

        paragraph_chunks: dict[str, list] = defaultdict(list)
        for row in results:
            paragraph_chunks[row["paragraph"]].append(row)

        sorted_paragraphs = sorted(paragraph_chunks.keys())
        total = len(sorted_paragraphs)
        page = sorted_paragraphs[offset:offset + limit]

        paragraphs = []
        for para_key in page:
            chunks = sorted(paragraph_chunks[para_key], key=lambda r: r["paragraph"])
            text = " ".join(r["text"] for r in chunks)
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
