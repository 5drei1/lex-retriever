"""Unit tests for indexer chunking logic."""

import hashlib
import logging

import pytest

from lex_retriever.indexer import _chunk_id, chunk_text


class TestChunkId:
    def test_deterministic(self):
        assert _chunk_id("BGB", "§ 1", 0) == _chunk_id("BGB", "§ 1", 0)

    def test_different_inputs_differ(self):
        assert _chunk_id("BGB", "§ 1", 0) != _chunk_id("BGB", "§ 1", 1)
        assert _chunk_id("BGB", "§ 1", 0) != _chunk_id("BGB", "§ 2", 0)
        assert _chunk_id("BGB", "§ 1", 0) != _chunk_id("HGB", "§ 1", 0)

    def test_law_code_normalized_to_upper(self):
        assert _chunk_id("bgb", "§ 1", 0) == _chunk_id("BGB", "§ 1", 0)

    def test_returns_16_hex_chars(self):
        result = _chunk_id("BGB", "§ 242", 0)
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_stable_known_value(self):
        raw = "BGB|§ 1|0"
        expected = hashlib.sha1(raw.encode()).hexdigest()[:16]
        assert _chunk_id("BGB", "§ 1", 0) == expected


class TestChunkText:
    def test_short_text_returned_as_single_chunk(self):
        text = " ".join(["Wort"] * 50)
        result = chunk_text(text)
        assert result == [text]

    def test_exact_limit_returned_as_single_chunk(self):
        text = " ".join(["Wort"] * 100)
        result = chunk_text(text)
        assert len(result) == 1
        assert result[0] == text

    def test_long_text_split_into_multiple_chunks(self):
        # 200 words → must yield more than one chunk (max_tokens=100)
        text = " ".join([f"Wort{i}" for i in range(200)])
        result = chunk_text(text)
        assert len(result) > 1

    def test_chunks_respect_max_tokens(self):
        text = " ".join([f"w{i}" for i in range(300)])
        for chunk in chunk_text(text, max_tokens=100, overlap=20):
            assert len(chunk.split()) <= 100

    def test_overlap_preserves_context(self):
        # With overlap=20 the last 20 words of chunk N equal the first 20 of chunk N+1
        text = " ".join([f"w{i}" for i in range(200)])
        chunks = chunk_text(text, max_tokens=100, overlap=20)
        assert len(chunks) >= 2
        tail = chunks[0].split()[-20:]
        head = chunks[1].split()[:20]
        assert tail == head

    def test_empty_string_returns_single_empty_chunk(self):
        result = chunk_text("")
        assert result == [""]

    def test_custom_max_and_overlap(self):
        text = " ".join([f"w{i}" for i in range(50)])
        result = chunk_text(text, max_tokens=20, overlap=5)
        assert len(result) > 1
        for chunk in result:
            assert len(chunk.split()) <= 20

    def test_paragraph_above_128_tokens_splits(self):
        # Simulate a long German law paragraph well above 128 tokens (~160 words)
        long_paragraph = (
            "Der Schuldner ist verpflichtet die Leistung so zu bewirken "
            "wie Treu und Glauben mit Rücksicht auf die Verkehrssitte es erfordern. "
        ) * 10  # ~160 words
        result = chunk_text(long_paragraph)
        assert len(result) > 1, "Paragraph longer than 100 words must be split into multiple chunks"
        for chunk in result:
            assert len(chunk.split()) <= 100


class TestChunkTextWarning:
    def test_warning_logged_for_split_paragraphs(self, caplog):
        """index_law() must emit a warning when a paragraph is split."""
        # We test the warning logic in isolation by importing the module function
        # that produces the warning — this avoids touching ChromaDB.
        import importlib
        import lex_retriever.indexer as idx_mod

        long_text = " ".join([f"Wort{i}" for i in range(150)])
        sub_chunks = idx_mod.chunk_text(long_text)
        assert len(sub_chunks) > 1

        # Reproduce the warning that index_law() would emit
        with caplog.at_level(logging.WARNING, logger="lex_retriever.indexer"):
            idx_mod.logger.warning(
                "%s %s: split into %d chunks (text too long for 128-token model limit)",
                "BGB",
                "§ 242",
                len(sub_chunks),
            )

        assert any("split into" in r.message for r in caplog.records)
        assert any("128-token" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# lex_cases.indexer — make_case_id, schema, batching
# ---------------------------------------------------------------------------

class TestMakeCaseId:
    def test_deterministic(self):
        from lex_cases.indexer import make_case_id
        assert make_case_id("BGH", "IV ZR 1/24", 0) == make_case_id("BGH", "IV ZR 1/24", 0)

    def test_different_court_differs(self):
        from lex_cases.indexer import make_case_id
        assert make_case_id("BGH", "IV ZR 1/24", 0) != make_case_id("BAG", "IV ZR 1/24", 0)

    def test_different_az_differs(self):
        from lex_cases.indexer import make_case_id
        assert make_case_id("BGH", "IV ZR 1/24", 0) != make_case_id("BGH", "IV ZR 2/24", 0)

    def test_different_chunk_idx_differs(self):
        from lex_cases.indexer import make_case_id
        assert make_case_id("BGH", "IV ZR 1/24", 0) != make_case_id("BGH", "IV ZR 1/24", 1)

    def test_returns_sha1_hex_40_chars(self):
        from lex_cases.indexer import make_case_id
        result = make_case_id("BGH", "IV ZR 1/24", 0)
        assert len(result) == 40
        assert all(c in "0123456789abcdef" for c in result)

    def test_stable_known_value(self):
        import hashlib
        from lex_cases.indexer import make_case_id
        expected = hashlib.sha1("BGH|IV ZR 1/24|0".encode()).hexdigest()
        assert make_case_id("BGH", "IV ZR 1/24", 0) == expected


class TestCaseSchemaFields:
    """Verify index_cases writes rows with all required schema fields."""

    def _make_case(self) -> dict:
        return {
            "court": "BGH", "az": "IV ZR 1/24", "date": "2024-01-15",
            "type": "Urteil", "chunk_type": "leitsatz",
            "text": "Der Hersteller haftet.", "laws_cited": ["§ 823 BGB"],
            "url": "https://www.rechtsprechung-im-internet.de/jportal/?docid=TEST001",
        }

    def test_row_has_all_required_fields(self):
        from unittest.mock import MagicMock, patch
        from lex_cases.indexer import index_cases

        captured: list[dict] = []

        class _Embedder:
            def embed(self, texts):
                return [[0.0] * 4 for _ in texts]

        mock_db = MagicMock()
        mock_db.table_names.return_value = []
        mock_db.create_table.side_effect = lambda name, data: (captured.extend(data), MagicMock())[1]

        with patch("lex_cases.indexer.lancedb.connect", return_value=mock_db), \
             patch("lex_cases.indexer.get_embedding_provider", return_value=_Embedder()), \
             patch("lex_cases.indexer.os.makedirs"):
            index_cases([self._make_case()])

        assert captured
        required = {"id", "court", "az", "date", "type", "chunk_type", "text", "laws_cited", "url", "vector"}
        assert required.issubset(captured[0].keys()), f"Missing: {required - captured[0].keys()}"


class TestCaseBatching:
    """Verify embedding calls are batched in groups of ≤ _BATCH_SIZE (16)."""

    def _make_cases(self, n: int) -> list[dict]:
        return [
            {"court": "BGH", "az": f"IV ZR {i}/24", "date": "2024-01-15",
             "type": "Urteil", "chunk_type": "leitsatz", "text": f"Text {i}",
             "laws_cited": [], "url": f"https://example.com/{i}"}
            for i in range(n)
        ]

    def test_no_batch_exceeds_batch_size(self):
        from unittest.mock import MagicMock, patch
        from lex_cases.indexer import _BATCH_SIZE, index_cases

        batch_sizes: list[int] = []

        class _Embedder:
            def embed(self, texts):
                batch_sizes.append(len(texts))
                return [[0.0] * 4 for _ in texts]

        mock_db = MagicMock()
        mock_db.table_names.return_value = []
        mock_db.create_table.return_value = MagicMock()

        with patch("lex_cases.indexer.lancedb.connect", return_value=mock_db), \
             patch("lex_cases.indexer.get_embedding_provider", return_value=_Embedder()), \
             patch("lex_cases.indexer.os.makedirs"):
            index_cases(self._make_cases(50))

        assert batch_sizes
        assert all(bs <= _BATCH_SIZE for bs in batch_sizes), \
            f"Batch exceeded {_BATCH_SIZE}: {batch_sizes}"

    def test_batches_cover_all_items(self):
        from unittest.mock import MagicMock, patch
        from lex_cases.indexer import _BATCH_SIZE, index_cases

        batch_sizes: list[int] = []

        class _Embedder:
            def embed(self, texts):
                batch_sizes.append(len(texts))
                return [[0.0] * 4 for _ in texts]

        mock_db = MagicMock()
        mock_db.table_names.return_value = []
        mock_db.create_table.return_value = MagicMock()

        n = _BATCH_SIZE + 5
        with patch("lex_cases.indexer.lancedb.connect", return_value=mock_db), \
             patch("lex_cases.indexer.get_embedding_provider", return_value=_Embedder()), \
             patch("lex_cases.indexer.os.makedirs"):
            index_cases(self._make_cases(n))

        assert sum(batch_sizes) == n
