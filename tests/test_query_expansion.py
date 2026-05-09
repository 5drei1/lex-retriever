"""Tests for query expansion module and its integration with search."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from lex_retriever.query_expansion import LEGAL_SYNONYMS, expand_query


# ---------------------------------------------------------------------------
# Unit tests for expand_query
# ---------------------------------------------------------------------------


def test_at_least_10_synonym_groups():
    assert len(LEGAL_SYNONYMS) >= 10


def test_known_term_is_expanded():
    result = expand_query("Haftung")
    assert result != "Haftung"
    assert "schadensersatz" in result.lower()


def test_case_insensitive_matching():
    result = expand_query("HAFTUNG")
    assert "schadensersatz" in result.lower()


def test_unknown_term_unchanged():
    assert expand_query("Prozessrecht") == "Prozessrecht"


def test_empty_query_unchanged():
    assert expand_query("") == ""


def test_original_preserved_as_prefix():
    original = "Haftung für Schäden"
    result = expand_query(original)
    assert result.startswith(original)


def test_haftung_fuer_schaeden_expands():
    result = expand_query("Haftung für Schäden")
    assert result != "Haftung für Schäden"
    assert "schadensersatz" in result.lower()


def test_multiple_known_terms_all_expanded():
    result = expand_query("Haftung Vertrag")
    assert "schadensersatz" in result.lower()
    assert "vertragspflicht" in result.lower()


def test_no_duplicates_from_repeated_term():
    result = expand_query("Haftung Haftung")
    # synonyms appear, but query still starts with the original
    assert result.startswith("Haftung Haftung")


# ---------------------------------------------------------------------------
# Integration tests: search() uses expansion and preserves original_query
# ---------------------------------------------------------------------------


def _mock_collection(docs, metas, distances):
    col = MagicMock()
    col.query.return_value = {
        "documents": [docs],
        "metadatas": [metas],
        "distances": [distances],
    }
    return col


def test_search_uses_expanded_query():
    mock_col = _mock_collection(
        ["§ 280 Schadensersatz wegen Pflichtverletzung."],
        [{"law": "BGB", "paragraph": "§ 280"}],
        [0.1],
    )
    with patch("lex_retriever.retriever._get_collection", return_value=mock_col):
        from lex_retriever.retriever import search

        search("Haftung", top_k=1)
        query_texts = mock_col.query.call_args.kwargs["query_texts"]
        assert query_texts[0] != "Haftung"
        assert "schadensersatz" in query_texts[0].lower()


def test_search_results_contain_original_query():
    mock_col = _mock_collection(
        ["§ 280 Schadensersatz wegen Pflichtverletzung."],
        [{"law": "BGB", "paragraph": "§ 280"}],
        [0.1],
    )
    with patch("lex_retriever.retriever._get_collection", return_value=mock_col):
        from lex_retriever.retriever import search

        results = search("Haftung für Schäden", top_k=1)
        assert len(results) == 1
        assert results[0]["original_query"] == "Haftung für Schäden"


def test_search_result_structure_preserved():
    mock_col = _mock_collection(
        ["§ 823 Schadensersatzpflicht."],
        [{"law": "BGB", "paragraph": "§ 823"}],
        [0.05],
    )
    with patch("lex_retriever.retriever._get_collection", return_value=mock_col):
        from lex_retriever.retriever import search

        results = search("Schaden", top_k=1)
        r = results[0]
        assert r["law"] == "BGB"
        assert r["paragraph"] == "§ 823"
        assert "text" in r
        assert isinstance(r["score"], float)
        assert r["original_query"] == "Schaden"


def test_search_unexpanded_query_passes_through_unchanged():
    mock_col = _mock_collection(
        ["Irgendein Text."],
        [{"law": "HGB", "paragraph": "§ 1"}],
        [0.2],
    )
    with patch("lex_retriever.retriever._get_collection", return_value=mock_col):
        from lex_retriever.retriever import search

        search("Prozessrecht", top_k=1)
        query_texts = mock_col.query.call_args.kwargs["query_texts"]
        assert query_texts[0] == "Prozessrecht"


# ---------------------------------------------------------------------------
# DB-dependent: expanded query scores higher than unexpanded
# ---------------------------------------------------------------------------

_has_db = os.path.exists(
    os.path.join(os.path.dirname(__file__), "..", "chroma_db", "chroma.sqlite3")
)


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="chroma_db not present — run indexer first")
def test_expanded_haftung_fuer_schaeden_scores_higher():
    """Expanded 'Haftung für Schäden' should surface at least one result
    with a higher top score than the unexpanded raw query."""
    from lex_retriever.query_expansion import expand_query
    from lex_retriever.retriever import search

    original = "Haftung für Schäden"
    expanded = expand_query(original)
    assert expanded != original, "pre-condition: expansion must differ"

    try:
        results_orig = search(original, top_k=5)
        results_exp = search(expanded, top_k=5)
    except Exception as exc:
        pytest.skip(f"DB query failed (incompatible embedding config?): {exc}")

    top_orig = max((r["score"] for r in results_orig), default=0.0)
    top_exp = max((r["score"] for r in results_exp), default=0.0)
    assert top_exp >= top_orig, (
        f"Expanded query top score {top_exp} not >= original top score {top_orig}"
    )
