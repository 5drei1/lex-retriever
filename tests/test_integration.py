"""Integration tests for lex_cases.

All tests require a populated LanceDB german_cases table.
Run them with: pytest -m requires_db
They are skipped by default when running the plain `pytest` suite.
"""

from __future__ import annotations

import os

import pytest

_LANCE_PATH = os.path.join(os.path.dirname(__file__), "..", "lancedb")
_HAS_CASES_DB = os.path.exists(os.path.join(_LANCE_PATH, "german_cases.lance"))


@pytest.mark.requires_db
@pytest.mark.skipif(
    not _HAS_CASES_DB,
    reason="LanceDB german_cases table not present — run `python -m lex_cases index-all` first",
)
class TestIndexCourtIntegration:
    def test_index_court_bgh_returns_positive_count(self):
        from lex_cases.indexer import index_court

        count = index_court("BGH")
        assert isinstance(count, int)

    def test_index_court_skips_already_indexed(self):
        from lex_cases.indexer import index_court

        count = index_court("BGH")
        assert count == 0, "Second call should find all cases already indexed and return 0"


@pytest.mark.requires_db
@pytest.mark.skipif(
    not _HAS_CASES_DB,
    reason="LanceDB german_cases table not present — run `python -m lex_cases index-all` first",
)
class TestSearchCaseLawIntegration:
    def test_search_returns_list(self):
        from lex_cases.retriever import LexCaseRetriever

        retriever = LexCaseRetriever()
        results = retriever.search("Produzentenhaftung", courts=["BGH"])
        assert isinstance(results, list)

    def test_search_result_structure(self):
        from lex_cases.retriever import LexCaseRetriever

        retriever = LexCaseRetriever()
        results = retriever.search("Produzentenhaftung", courts=["BGH"], top_k=3)
        for r in results:
            for key in ("court", "az", "date", "type", "leitsatz", "laws_cited", "score", "url"):
                assert key in r, f"Missing key in result: {key}"

    def test_search_score_in_range(self):
        from lex_cases.retriever import LexCaseRetriever

        retriever = LexCaseRetriever()
        results = retriever.search("Schadensersatz")
        for r in results:
            assert 0.0 <= r["score"] <= 1.0

    def test_court_filter_respected(self):
        from lex_cases.retriever import LexCaseRetriever

        retriever = LexCaseRetriever()
        results = retriever.search("Urteil", courts=["BGH"], top_k=5)
        for r in results:
            assert r["court"] == "Bundesgerichtshof" or r["court"] == "BGH"
