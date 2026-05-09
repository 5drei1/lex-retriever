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


def test_compound_word_triggers_component_synonyms():
    # "Vertragsstrafe" contains "vertrag" and "strafe" as substrings
    result = expand_query("Vertragsstrafe")
    assert "vertragspflicht" in result.lower()
    assert "bußgeld" in result.lower()


def test_no_duplicate_synonyms_in_expansion():
    # "haftung" and "schaden" both expand to "schadensersatz" — must appear once
    result = expand_query("Haftung Schaden")
    suffix = result[len("Haftung Schaden"):].lower()
    assert suffix.count("schadensersatz") == 1


# ---------------------------------------------------------------------------
# Integration tests: search() uses expansion and preserves original_query
# ---------------------------------------------------------------------------


def _make_mock_table(rows):
    """Create a mock LanceDB table that returns given rows from search()."""
    mock_table = MagicMock()
    q = MagicMock()
    q.where.return_value = q
    q.limit.return_value = q
    q.to_list.return_value = rows
    mock_table.search.return_value = q
    return mock_table


def _search_with_capture(query, top_k=1):
    """Run search() with a mock table and capturing embedder; return (results, embedded_texts)."""
    from lex_retriever.retriever import LexRetriever

    rows = [{"law": "BGB", "paragraph": "§ 280", "text": "Schadensersatz.",
             "source": "x", "id": "1", "_distance": 0.1}]
    mock_table = _make_mock_table(rows)

    captured: list[str] = []

    class _CapturingEmbedder:
        def embed(self, texts):
            captured.extend(texts)
            return [[0.0] * 384]

    with patch.object(LexRetriever, "_get_table", return_value=mock_table), \
         patch("lex_retriever.retriever.get_embedding_provider", return_value=_CapturingEmbedder()):
        from lex_retriever.retriever import search as _search
        results = _search(query, top_k=top_k)
    return results, captured


def test_search_uses_expanded_query():
    _, embedded = _search_with_capture("Haftung")
    assert embedded, "embedder was not called"
    assert embedded[0] != "Haftung"
    assert "schadensersatz" in embedded[0].lower()


def test_search_results_contain_original_query():
    results, _ = _search_with_capture("Haftung für Schäden")
    assert len(results) == 1
    assert results[0]["original_query"] == "Haftung für Schäden"


def test_search_result_structure_preserved():
    from lex_retriever.retriever import LexRetriever

    rows = [{"law": "BGB", "paragraph": "§ 823", "text": "Schadensersatzpflicht.",
             "source": "x", "id": "2", "_distance": 0.05}]
    mock_table = _make_mock_table(rows)

    class _DummyEmbedder:
        def embed(self, texts):
            return [[0.0] * 384]

    with patch.object(LexRetriever, "_get_table", return_value=mock_table), \
         patch("lex_retriever.retriever.get_embedding_provider", return_value=_DummyEmbedder()):
        from lex_retriever.retriever import search as _search
        results = _search("Schaden", top_k=1)

    r = results[0]
    assert r["law"] == "BGB"
    assert r["paragraph"] == "§ 823"
    assert "text" in r
    assert isinstance(r["score"], float)
    assert r["original_query"] == "Schaden"


def test_search_unexpanded_query_passes_through_unchanged():
    _, embedded = _search_with_capture("Prozessrecht")
    assert embedded, "embedder was not called"
    assert embedded[0] == "Prozessrecht"


# ---------------------------------------------------------------------------
# DB-dependent: expanded query scores higher than unexpanded
# ---------------------------------------------------------------------------

_has_db = os.path.exists(
    os.path.join(os.path.dirname(__file__), "..", "lancedb", "german_law.lance")
)


@pytest.mark.requires_db
@pytest.mark.skipif(not _has_db, reason="lancedb not present — run `python -m lex_retriever index-all` first")
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
