"""Tests for get_full_law() — paginated law retrieval."""

import os
import pytest

_has_db = os.path.exists(os.path.join(os.path.dirname(__file__), "..", "chroma_db"))


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="chroma_db not present — run `python -m lex_retriever.indexer` first")
def test_get_full_law_response_structure():
    from lex_retriever import get_full_law
    result = get_full_law("BGB", offset=0, limit=50)
    assert isinstance(result, dict)
    assert "law" in result
    assert "total_paragraphs" in result
    assert "offset" in result
    assert "paragraphs" in result
    assert result["law"] == "BGB"
    assert result["offset"] == 0
    assert isinstance(result["total_paragraphs"], int)
    assert isinstance(result["paragraphs"], list)


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="chroma_db not present — run `python -m lex_retriever.indexer` first")
def test_get_full_law_pagination_limit():
    from lex_retriever import get_full_law
    result = get_full_law("BGB", offset=0, limit=2)
    assert len(result["paragraphs"]) == 2
    for p in result["paragraphs"]:
        assert "paragraph" in p
        assert "text" in p


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="chroma_db not present — run `python -m lex_retriever.indexer` first")
def test_get_full_law_pagination_offset():
    from lex_retriever import get_full_law
    page1 = get_full_law("BGB", offset=0, limit=2)
    page2 = get_full_law("BGB", offset=2, limit=2)
    assert page1["paragraphs"] != page2["paragraphs"]
    p1_keys = {p["paragraph"] for p in page1["paragraphs"]}
    p2_keys = {p["paragraph"] for p in page2["paragraphs"]}
    assert p1_keys.isdisjoint(p2_keys)


def test_get_full_law_is_callable():
    from lex_retriever import get_full_law
    assert callable(get_full_law)
