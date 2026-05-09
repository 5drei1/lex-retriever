"""Tests for retriever and search_law interface."""

import hashlib
import os
import random
from unittest.mock import patch

import chromadb
import pytest

import lex_retriever.retriever as _retriever_mod

_has_db = os.path.exists(os.path.join(os.path.dirname(__file__), "..", "chroma_db"))


class _DeterministicEF:
    """Minimal deterministic embedding function — no model download needed."""

    def _embed(self, input: list[str]) -> list[list[float]]:
        results = []
        for text in input:
            seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**31)
            rng = random.Random(seed)
            results.append([rng.uniform(-1, 1) for _ in range(384)])
        return results

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self._embed(input)

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self._embed(input)


@pytest.fixture
def _gmbhg_collection():
    """In-memory ChromaDB collection with GmbHG chunks; patches retriever module globals."""
    client = chromadb.EphemeralClient()
    ef = _DeterministicEF()
    collection = client.create_collection("german_law", embedding_function=ef)
    collection.add(
        ids=["gmbhg-1", "gmbhg-2", "gmbhg-3"],
        documents=[
            "Der Geschäftsführer ist zur Führung der Geschäfte der Gesellschaft bestellt.",
            "Die Gesellschafter der GmbH bestellen den Geschäftsführer durch Beschluss.",
            "Der Geschäftsführer vertritt die Gesellschaft gerichtlich und außergerichtlich.",
        ],
        metadatas=[
            {"law": "GmbHG", "paragraph": "§ 6 Abs. 1"},
            {"law": "GmbHG", "paragraph": "§ 6 Abs. 2"},
            {"law": "GmbHG", "paragraph": "§ 35 Abs. 1"},
        ],
    )

    old_collection = _retriever_mod._collection
    old_client = _retriever_mod._client
    old_key = _retriever_mod._collection_config_key

    _retriever_mod._collection = collection
    _retriever_mod._client = client
    _retriever_mod._collection_config_key = "[]"

    with patch("lex_retriever.tool._load_embedding_config", return_value={}):
        yield

    _retriever_mod._collection = old_collection
    _retriever_mod._client = old_client
    _retriever_mod._collection_config_key = old_key


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="chroma_db not present — run `python -m lex_retriever.indexer` first")
def test_search_law_returns_list():
    from lex_retriever import search_law
    results = search_law("Haftung", top_k=3)
    assert isinstance(results, list)


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="chroma_db not present — run `python -m lex_retriever.indexer` first")
def test_search_law_result_structure():
    from lex_retriever import search_law
    results = search_law("Vertragspflichten", top_k=2)
    for r in results:
        assert "law" in r
        assert "paragraph" in r
        assert "text" in r
        assert "score" in r
        assert isinstance(r["score"], float)
        assert 0.0 <= r["score"] <= 1.0


def test_search_law_with_filter(_gmbhg_collection):
    from lex_retriever import search_law
    results = search_law("Geschäftsführer", laws=["GmbHG"], top_k=3)
    assert results, "expected at least one result"
    for r in results:
        assert r["law"] == "GmbHG"


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="chroma_db not present — run `python -m lex_retriever.indexer` first")
def test_search_law_top_k():
    from lex_retriever import search_law
    results = search_law("Paragraphentest", top_k=3)
    assert len(results) <= 3


def test_import_works():
    """Ensure the public interface is importable."""
    from lex_retriever import search_law, index_law, index_all_laws
    assert callable(search_law)
    assert callable(index_law)
    assert callable(index_all_laws)
