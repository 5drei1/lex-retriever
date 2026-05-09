"""Tests for retriever and search_law interface."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from lex_retriever.retriever import LexRetriever

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
        assert r["law"] == "GMBHG"


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


def test_lex_retriever_instances_have_isolated_state():
    """Each LexRetriever instance must not share _collection with another."""
    r1 = LexRetriever(chroma_path="/tmp/path_a", embedding_config={"provider": "sentence-transformers"})
    r2 = LexRetriever(chroma_path="/tmp/path_b", embedding_config={"provider": "sentence-transformers"})
    assert r1._collection is None
    assert r2._collection is None
    assert r1 is not r2
    assert r1._chroma_path != r2._chroma_path


def test_lex_retriever_lazy_collection_init():
    """_collection stays None until search() is called."""
    r = LexRetriever(chroma_path="/tmp/fake", embedding_config=None)
    assert r._collection is None


def _make_mock_collection():
    col = MagicMock()
    col.query.return_value = {
        "documents": [["§1 Text"]],
        "metadatas": [[{"law": "BGB", "paragraph": "§1"}]],
        "distances": [[0.1]],
    }
    return col


@patch("lex_retriever.retriever.chromadb.PersistentClient")
@patch("lex_retriever.retriever.get_chroma_embedding_function")
def test_lex_retriever_search_uses_cosine_metadata(mock_ef, mock_client_cls):
    """get_or_create_collection must pass hnsw:space=cosine."""
    mock_col = _make_mock_collection()
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_col
    mock_client_cls.return_value = mock_client

    r = LexRetriever(chroma_path="/tmp/fake")
    r.search("Haftung", top_k=1)

    mock_client.get_or_create_collection.assert_called_once()
    call_kwargs = mock_client.get_or_create_collection.call_args
    assert call_kwargs.kwargs.get("metadata") == {"hnsw:space": "cosine"}


@patch("lex_retriever.retriever.chromadb.PersistentClient")
@patch("lex_retriever.retriever.get_chroma_embedding_function")
def test_two_instances_do_not_share_collection(mock_ef, mock_client_cls):
    """Two LexRetriever instances each get their own collection object."""
    col_a = _make_mock_collection()
    col_b = _make_mock_collection()
    client_a, client_b = MagicMock(), MagicMock()
    client_a.get_or_create_collection.return_value = col_a
    client_b.get_or_create_collection.return_value = col_b
    mock_client_cls.side_effect = [client_a, client_b]

    r1 = LexRetriever(chroma_path="/tmp/a")
    r2 = LexRetriever(chroma_path="/tmp/b")
    r1.search("test", top_k=1)
    r2.search("test", top_k=1)

    assert r1._collection is col_a
    assert r2._collection is col_b
    assert r1._collection is not r2._collection


@patch("lex_retriever.retriever.chromadb.PersistentClient")
@patch("lex_retriever.retriever.get_chroma_embedding_function")
def test_module_search_wrapper_still_works(mock_ef, mock_client_cls):
    """Module-level search() remains callable and returns results."""
    from lex_retriever.retriever import search

    mock_col = _make_mock_collection()
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_col
    mock_client_cls.return_value = mock_client

    results = search("Haftung", top_k=1)
    assert isinstance(results, list)
    assert results[0]["law"] == "BGB"
