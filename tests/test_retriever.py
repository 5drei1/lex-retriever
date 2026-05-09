"""Tests for retriever and search_law interface."""

import hashlib
import os
import random
from unittest.mock import patch

import pytest

import lex_retriever.retriever as _retriever_mod

_has_db = os.path.exists(os.path.join(os.path.dirname(__file__), "..", "lancedb", "german_law.lance"))


def _det_vector(text: str) -> list[float]:
    """Deterministic 384-dim vector derived from text hash — no model download needed."""
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**31)
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(384)]


@pytest.fixture
def _gmbhg_collection(tmp_path):
    """LanceDB table with GmbHG chunks; patches LexRetriever._get_table and get_embedding_provider."""
    import lancedb

    texts = [
        "Der Geschäftsführer ist zur Führung der Geschäfte der Gesellschaft bestellt.",
        "Die Gesellschafter der GmbH bestellen den Geschäftsführer durch Beschluss.",
        "Der Geschäftsführer vertritt die Gesellschaft gerichtlich und außergerichtlich.",
    ]

    rows = [
        {"id": "gmbhg-1", "law": "GMBHG", "paragraph": "§ 6 Abs. 1",
         "text": texts[0], "source": "test", "vector": _det_vector(texts[0])},
        {"id": "gmbhg-2", "law": "GMBHG", "paragraph": "§ 6 Abs. 2",
         "text": texts[1], "source": "test", "vector": _det_vector(texts[1])},
        {"id": "gmbhg-3", "law": "GMBHG", "paragraph": "§ 35 Abs. 1",
         "text": texts[2], "source": "test", "vector": _det_vector(texts[2])},
    ]

    db = lancedb.connect(str(tmp_path))
    table = db.create_table("german_law", data=rows)

    class _MockEmbedder:
        def embed(self, texts: list[str]) -> list[list[float]]:
            return [_det_vector(t) for t in texts]

    from lex_retriever.retriever import LexRetriever

    with patch.object(LexRetriever, "_get_table", return_value=table), \
         patch("lex_retriever.retriever.get_embedding_provider", return_value=_MockEmbedder()), \
         patch("lex_retriever.tool._load_embedding_config", return_value={}):
        yield


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="lancedb not present — run `python -m lex_retriever index-all` first")
def test_search_law_returns_list():
    from lex_retriever import search_law
    results = search_law("Haftung", top_k=3)
    assert isinstance(results, list)


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="lancedb not present — run `python -m lex_retriever index-all` first")
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
        assert r["law"] == "GMBHG"


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="lancedb not present — run `python -m lex_retriever index-all` first")
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
