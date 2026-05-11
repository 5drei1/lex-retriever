"""Tests for retriever and search_law interface."""

import hashlib
import os
import random
from unittest.mock import MagicMock, patch

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
    """LanceDB table with GmbHG chunks (ref_id schema, no stored text).

    Patches LexRetriever._get_table, get_embedding_provider, and
    _lex_retriever.retriever._fetch_law_chunks to avoid network calls.
    """
    import lancedb

    texts = [
        "Der Geschäftsführer ist zur Führung der Geschäfte der Gesellschaft bestellt.",
        "Die Gesellschafter der GmbH bestellen den Geschäftsführer durch Beschluss.",
        "Der Geschäftsführer vertritt die Gesellschaft gerichtlich und außergerichtlich.",
    ]
    paragraphs = ["§ 6 Abs. 1", "§ 6 Abs. 2", "§ 35 Abs. 1"]

    rows = [
        {"id": "gmbhg-1", "law": "GMBHG", "paragraph": paragraphs[0],
         "ref_id": "gesetze-im-internet.de/GMBHG", "vector": _det_vector(texts[0])},
        {"id": "gmbhg-2", "law": "GMBHG", "paragraph": paragraphs[1],
         "ref_id": "gesetze-im-internet.de/GMBHG", "vector": _det_vector(texts[1])},
        {"id": "gmbhg-3", "law": "GMBHG", "paragraph": paragraphs[2],
         "ref_id": "gesetze-im-internet.de/GMBHG", "vector": _det_vector(texts[2])},
    ]

    db = lancedb.connect(str(tmp_path))
    table = db.create_table("german_law", data=rows)

    class _MockEmbedder:
        def embed(self, texts: list[str]) -> list[list[float]]:
            return [_det_vector(t) for t in texts]

    # Provide on-demand text without network calls
    fake_chunks = [
        {"paragraph": p, "text": t, "source": "gesetze-im-internet.de/GMBHG"}
        for p, t in zip(paragraphs, texts)
    ]

    from lex_retriever.retriever import LexRetriever

    with patch.object(LexRetriever, "_get_table", return_value=table), \
         patch("lex_retriever.retriever.get_embedding_provider", return_value=_MockEmbedder()), \
         patch("lex_retriever.retriever._fetch_law_chunks", return_value=fake_chunks), \
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


# ---------------------------------------------------------------------------
# On-demand text fetching — new ref_id schema
# ---------------------------------------------------------------------------

class TestOnDemandTextFetching:
    """Verify that LexRetriever fetches text on demand via _fetch_law_chunks."""

    def _make_retriever_with_table(self, rows):
        """Return a LexRetriever backed by in-memory table rows (no LanceDB disk I/O)."""
        from unittest.mock import MagicMock
        from lex_retriever.retriever import LexRetriever

        class _MockQuery:
            def __init__(self, data):
                self._data = data

            def search(self, *args, **kwargs): return self
            def where(self, clause):
                # Very minimal WHERE filtering for law equality
                if "law = " in clause:
                    law = clause.split("'")[1]
                    self._data = [r for r in self._data if r.get("law") == law]
                return self

            def limit(self, n): return self
            def to_list(self): return list(self._data)

        class _MockEmbedder:
            def embed(self, texts): return [_det_vector(t) for t in texts]

        r = LexRetriever.__new__(LexRetriever)
        r._lance_path = "/tmp/test"
        r._embedding_config = None
        r._table = _MockQuery(rows)
        r._embedder = _MockEmbedder()
        r._text_cache = {}
        return r

    def test_search_fetches_text_on_demand(self):
        from unittest.mock import patch

        rows = [{"law": "TESTLAW", "paragraph": "§ 1",
                 "ref_id": "gesetze-im-internet.de/TESTLAW", "_distance": 0.2}]
        fake_chunks = [{"paragraph": "§ 1", "text": "Gesetzestext §1", "source": "x"}]

        r = self._make_retriever_with_table(rows)

        with patch("lex_retriever.retriever.expand_query", return_value="test"), \
             patch("lex_retriever.retriever._fetch_law_chunks", return_value=fake_chunks):
            results = r.search("test", laws=["TESTLAW"])

        assert results
        assert results[0]["text"] == "Gesetzestext §1"
        assert results[0]["law"] == "TESTLAW"

    def test_search_result_contains_ref_id(self):
        from unittest.mock import patch

        rows = [{"law": "TESTLAW", "paragraph": "§ 2",
                 "ref_id": "gesetze-im-internet.de/TESTLAW", "_distance": 0.1}]
        fake_chunks = [{"paragraph": "§ 2", "text": "Text §2", "source": "x"}]

        r = self._make_retriever_with_table(rows)

        with patch("lex_retriever.retriever.expand_query", return_value="test"), \
             patch("lex_retriever.retriever._fetch_law_chunks", return_value=fake_chunks):
            results = r.search("test", laws=["TESTLAW"])

        assert results
        assert results[0].get("ref_id") == "gesetze-im-internet.de/TESTLAW"

    def test_text_cached_per_law(self):
        """_fetch_law_chunks should only be called once per law, even for multiple results."""
        from unittest.mock import patch, MagicMock

        rows = [
            {"law": "TESTLAW", "paragraph": "§ 1",
             "ref_id": "gesetze-im-internet.de/TESTLAW", "_distance": 0.1},
            {"law": "TESTLAW", "paragraph": "§ 2",
             "ref_id": "gesetze-im-internet.de/TESTLAW", "_distance": 0.2},
        ]
        fake_chunks = [
            {"paragraph": "§ 1", "text": "Text §1", "source": "x"},
            {"paragraph": "§ 2", "text": "Text §2", "source": "x"},
        ]

        r = self._make_retriever_with_table(rows)
        fetch_mock = MagicMock(return_value=fake_chunks)

        with patch("lex_retriever.retriever.expand_query", return_value="test"), \
             patch("lex_retriever.retriever._fetch_law_chunks", fetch_mock):
            results = r.search("test", laws=["TESTLAW"])

        assert len(results) == 2
        fetch_mock.assert_called_once_with("TESTLAW")


# ---------------------------------------------------------------------------
# lex_cases.retriever — LexCaseRetriever
# ---------------------------------------------------------------------------

def _case_vector(text: str) -> list[float]:
    import hashlib
    import random
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**31)
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(384)]


class _CaseMockQuery:
    def __init__(self, rows):
        self._rows = rows

    def limit(self, n):
        return self

    def to_list(self):
        return list(self._rows)


_CASE_ROWS = [
    {"court": "BGH",  "az": "IV ZR 1/24",   "date": "2024-01-15", "type": "Urteil",
     "leitsatz": "Produzentenhaftung.", "laws_cited": ["§ 823 BGB"], "url": "https://ex.com/1",
     "vector": _case_vector("a"), "_distance": 0.1},
    {"court": "BAG",  "az": "1 AZR 100/23", "date": "2023-06-01", "type": "Urteil",
     "leitsatz": "Kündigungsschutz.", "laws_cited": ["§ 613a BGB"], "url": "https://ex.com/2",
     "vector": _case_vector("b"), "_distance": 0.2},
    {"court": "BGH",  "az": "II ZR 50/22",  "date": "2022-03-01", "type": "Urteil",
     "leitsatz": "Pflichtverletzung.", "laws_cited": ["§ 280 BGB"], "url": "https://ex.com/3",
     "vector": _case_vector("c"), "_distance": 0.3},
]


@pytest.fixture
def case_retriever():
    from unittest.mock import MagicMock
    from lex_cases.retriever import LexCaseRetriever

    class _MockEmbedder:
        def embed(self, texts):
            return [_case_vector(t) for t in texts]

    r = LexCaseRetriever(db_path="/tmp/test_case_lancedb", embedding_provider=_MockEmbedder())
    mock_table = MagicMock()
    mock_table.search = MagicMock(return_value=_CaseMockQuery(_CASE_ROWS))
    r._table = mock_table
    return r, mock_table


class TestLexCaseRetrieverSearch:
    def test_returns_list(self, case_retriever):
        r, _ = case_retriever
        assert isinstance(r.search("Haftung"), list)

    def test_courts_filter(self, case_retriever):
        r, mock_table = case_retriever
        mock_table.search = MagicMock(return_value=_CaseMockQuery(_CASE_ROWS))
        results = r.search("Haftung", courts=["BGH"])
        assert results
        assert all(res["court"] == "BGH" for res in results)

    def test_date_from_filter(self, case_retriever):
        r, mock_table = case_retriever
        mock_table.search = MagicMock(return_value=_CaseMockQuery(_CASE_ROWS))
        results = r.search("Haftung", date_from="2024-01-01")
        assert all(res["date"] >= "2024-01-01" for res in results)

    def test_date_to_filter(self, case_retriever):
        r, mock_table = case_retriever
        mock_table.search = MagicMock(return_value=_CaseMockQuery(_CASE_ROWS))
        results = r.search("Haftung", date_to="2022-12-31")
        assert all(res["date"] <= "2022-12-31" for res in results)

    def test_score_in_range(self, case_retriever):
        r, _ = case_retriever
        for res in r.search("Haftung"):
            assert 0.0 <= res["score"] <= 1.0


class TestGetCasesCitingLaw:
    def test_filters_by_law_and_paragraph(self, case_retriever):
        r, mock_table = case_retriever
        mock_table.search = MagicMock(return_value=_CaseMockQuery(_CASE_ROWS))
        results = r.get_cases_citing_law("BGB", "§ 823")
        assert results
        assert all("§ 823 BGB" in res["laws_cited"] for res in results)

    def test_no_match_returns_empty(self, case_retriever):
        r, mock_table = case_retriever
        mock_table.search = MagicMock(return_value=_CaseMockQuery(_CASE_ROWS))
        assert r.get_cases_citing_law("ZPO", "§ 91") == []
