"""Tests for retriever and search_law interface."""

import os
import pytest

_has_db = os.path.exists(os.path.join(os.path.dirname(__file__), "..", "chroma_db"))


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


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="chroma_db not present — run `python -m lex_retriever.indexer` first")
def test_search_law_with_filter():
    from lex_retriever import search_law
    results = search_law("Geschäftsführer", laws=["GmbHG"], top_k=5)
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
