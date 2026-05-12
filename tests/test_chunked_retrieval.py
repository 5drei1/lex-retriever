"""Tests for chunked paragraph text retrieval.

Verifies that LexRetriever._get_text() returns non-empty text for paragraph
keys with [N/M] chunk suffixes, which providers do not include in their output.
No external dependencies or persistent DB required.
"""

from __future__ import annotations

import hashlib
import random
from unittest.mock import MagicMock, patch

# 150-word paragraph — exceeds the 100-word chunk limit, so the indexer splits
# it into [1/2] and [2/2].  Deterministic so tests are stable.
_LONG_TEXT = " ".join(f"Wort{i}" for i in range(150))
_SHORT_TEXT = "Ein kurzer Gesetzestext ohne Aufteilung."


def _det_vector(text: str) -> list[float]:
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**31)
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(384)]


class _MockEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_det_vector(t) for t in texts]


class _MockQuery:
    """Minimal LanceDB query mock used by LexRetriever.search()."""

    def __init__(self, rows: list[dict]):
        self._rows = rows

    def search(self, *args, **kwargs):
        return self

    def where(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    def to_list(self):
        return list(self._rows)


def _make_retriever(table_rows: list[dict] | None = None):
    """Return a LexRetriever with all external deps replaced by mocks."""
    from lex_retriever.retriever import LexRetriever

    r = LexRetriever.__new__(LexRetriever)
    r._lance_path = "/nonexistent"
    r._embedding_config = None
    r._embedder = _MockEmbedder()
    r._text_cache = {}
    r._table = _MockQuery(table_rows or [])
    return r


# ---------------------------------------------------------------------------
# Unit tests for _get_text() directly
# ---------------------------------------------------------------------------

class TestGetTextChunkedFallback:
    def test_direct_key_returns_text(self):
        r = _make_retriever()
        r._text_cache["BGB"] = {"§ 1": _SHORT_TEXT}
        assert r._get_text("BGB", "§ 1") == _SHORT_TEXT

    def test_unknown_key_returns_empty(self):
        r = _make_retriever()
        r._text_cache["BGB"] = {"§ 1": _SHORT_TEXT}
        assert r._get_text("BGB", "§ 99") == ""

    def test_chunked_key_first_chunk_nonempty(self):
        """[1/2] suffix → should return the first sub-chunk of the base paragraph."""
        r = _make_retriever()
        r._text_cache["BGB"] = {"§ 100": _LONG_TEXT}
        result = r._get_text("BGB", "§ 100 [1/2]")
        assert result != "", "Expected non-empty text for [1/2] chunked key"

    def test_chunked_key_second_chunk_nonempty(self):
        """[2/2] suffix → should return the second sub-chunk of the base paragraph."""
        r = _make_retriever()
        r._text_cache["BGB"] = {"§ 100": _LONG_TEXT}
        result = r._get_text("BGB", "§ 100 [2/2]")
        assert result != "", "Expected non-empty text for [2/2] chunked key"

    def test_chunked_key_matches_when_paragraph_whitespace_differs(self):
        """Paragraph keys with newlines/multi-space must match normalized chunked lookups."""
        r = _make_retriever()
        r._text_cache["BGB"] = {
            "§ 281 (Schadensersatz statt der Leistung wegen nicht oder nicht wie geschuldet\n"
            "erbrachter Leistung)": _LONG_TEXT
        }
        result = r._get_text(
            "BGB",
            "§ 281 (Schadensersatz statt der Leistung wegen nicht oder nicht wie geschuldet "
            "erbrachter Leistung) [1/2]",
        )
        assert result != "", "Expected non-empty text despite whitespace differences in paragraph key"

    def test_chunked_chunks_are_different(self):
        """[1/2] and [2/2] should return different text (overlap is partial, not identical)."""
        r = _make_retriever()
        r._text_cache["BGB"] = {"§ 100": _LONG_TEXT}
        chunk1 = r._get_text("BGB", "§ 100 [1/2]")
        chunk2 = r._get_text("BGB", "§ 100 [2/2]")
        assert chunk1 != chunk2

    def test_chunked_key_out_of_range_returns_empty(self):
        """[5/2] is out of range — should return empty gracefully."""
        r = _make_retriever()
        r._text_cache["BGB"] = {"§ 100": _LONG_TEXT}
        result = r._get_text("BGB", "§ 100 [5/2]")
        assert result == ""

    def test_base_key_missing_returns_empty(self):
        """Chunked key whose base paragraph is absent → returns empty without crashing."""
        r = _make_retriever()
        r._text_cache["BGB"] = {}
        result = r._get_text("BGB", "§ 99 [1/2]")
        assert result == ""

    def test_cache_populated_from_fetch(self):
        """_get_text triggers _build_text_index when law_code not yet cached."""
        r = _make_retriever()
        fake_chunks = [{"paragraph": "§ 5", "text": _SHORT_TEXT, "source": "x"}]
        with patch("lex_retriever.retriever._fetch_law_chunks", return_value=fake_chunks):
            result = r._get_text("TESTLAW", "§ 5")
        assert result == _SHORT_TEXT


# ---------------------------------------------------------------------------
# Integration: search() returns non-empty text for chunked paragraph results
# ---------------------------------------------------------------------------

class TestSearchChunkedParagraphs:
    """search() must not produce empty-text results for chunked paragraph keys."""

    def _run_search(self, rows: list[dict], fake_chunks: list[dict]) -> list[dict]:
        r = _make_retriever(table_rows=rows)
        with patch("lex_retriever.retriever.expand_query", return_value="test"), \
             patch("lex_retriever.retriever._fetch_law_chunks", return_value=fake_chunks):
            return r.search("test")

    def test_all_results_have_nonempty_text(self):
        rows = [
            {"law": "BGB", "paragraph": "§ 100 [1/2]",
             "ref_id": "gesetze-im-internet.de/BGB", "_distance": 0.2},
            {"law": "BGB", "paragraph": "§ 100 [2/2]",
             "ref_id": "gesetze-im-internet.de/BGB", "_distance": 0.3},
            {"law": "BGB", "paragraph": "§ 1",
             "ref_id": "gesetze-im-internet.de/BGB", "_distance": 0.4},
        ]
        fake_chunks = [
            {"paragraph": "§ 100", "text": _LONG_TEXT,  "source": "gesetze-im-internet.de/BGB"},
            {"paragraph": "§ 1",   "text": _SHORT_TEXT, "source": "gesetze-im-internet.de/BGB"},
        ]
        results = self._run_search(rows, fake_chunks)
        assert len(results) == 3
        for r in results:
            assert r["text"] != "", f"Empty text for paragraph: {r['paragraph']}"

    def test_empty_text_rate_is_zero(self):
        """Regression: 37.1% empty-text rate must be 0%."""
        rows = [
            {"law": "BGB", "paragraph": f"§ 50 [{i+1}/3]",
             "ref_id": "src", "_distance": 0.1 * i}
            for i in range(3)
        ]
        long_text_200 = " ".join(f"Wort{i}" for i in range(200))
        fake_chunks = [{"paragraph": "§ 50", "text": long_text_200, "source": "src"}]
        results = self._run_search(rows, fake_chunks)
        empty = [r for r in results if not r["text"]]
        assert len(empty) == 0, f"Got {len(empty)}/{len(results)} empty-text results"

    def test_single_chunk_paragraph_unaffected(self):
        """Paragraphs without [N/M] suffix continue to work via direct lookup."""
        rows = [{"law": "BGB", "paragraph": "§ 1",
                 "ref_id": "src", "_distance": 0.1}]
        fake_chunks = [{"paragraph": "§ 1", "text": _SHORT_TEXT, "source": "src"}]
        results = self._run_search(rows, fake_chunks)
        assert results[0]["text"] == _SHORT_TEXT
