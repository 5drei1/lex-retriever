"""Tests for get_paragraph — direct norm retrieval."""

import os
import pytest

_has_db = os.path.exists(os.path.join(os.path.dirname(__file__), "..", "chroma_db"))


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="chroma_db not present — run `python -m lex_retriever.indexer` first")
def test_get_paragraph_returns_dict_with_required_keys():
    from lex_retriever import get_paragraph
    result = get_paragraph("BGB", "§ 242")
    assert result is not None
    assert "law" in result
    assert "paragraph" in result
    assert "text" in result
    assert "chunks" in result
    assert result["law"] == "BGB"
    assert result["paragraph"] == "§ 242"
    assert isinstance(result["text"], str)
    assert len(result["text"]) > 0
    assert isinstance(result["chunks"], int)
    assert result["chunks"] >= 1


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="chroma_db not present — run `python -m lex_retriever.indexer` first")
def test_get_paragraph_missing_returns_none():
    from lex_retriever import get_paragraph
    result = get_paragraph("BGB", "§ 99999")
    assert result is None


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="chroma_db not present — run `python -m lex_retriever.indexer` first")
def test_get_paragraph_law_uppercased():
    from lex_retriever import get_paragraph
    result = get_paragraph("bgb", "§ 242")
    if result is not None:
        assert result["law"] == "BGB"


def test_get_paragraph_is_callable():
    from lex_retriever import get_paragraph
    assert callable(get_paragraph)
