"""Unit tests for lex_cases.indexer."""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, call, patch

import pytest


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

    def test_returns_sha1_hex(self):
        from lex_cases.indexer import make_case_id
        result = make_case_id("BGH", "IV ZR 1/24", 0)
        assert len(result) == 40
        assert all(c in "0123456789abcdef" for c in result)

    def test_stable_known_value(self):
        from lex_cases.indexer import make_case_id
        expected = hashlib.sha1("BGH|IV ZR 1/24|0".encode()).hexdigest()
        assert make_case_id("BGH", "IV ZR 1/24", 0) == expected


class TestIndexCasesSchema:
    """Verify that index_cases writes rows with all required schema fields."""

    def _make_case(self, **overrides) -> dict:
        base = {
            "court": "BGH",
            "az": "IV ZR 1/24",
            "date": "2024-01-15",
            "type": "Urteil",
            "chunk_type": "leitsatz",
            "text": "Der Hersteller haftet.",
            "laws_cited": ["§ 823 BGB"],
            "url": "https://www.rechtsprechung-im-internet.de/jportal/?docid=TEST001",
        }
        base.update(overrides)
        return base

    def test_row_has_all_required_fields(self):
        from lex_cases.indexer import index_cases

        captured_rows: list[dict] = []

        class _MockEmbedder:
            def embed(self, texts):
                return [[0.0] * 4 for _ in texts]

        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table_names.return_value = []
        mock_db.create_table.return_value = mock_table

        def _capture_create(name, data):
            captured_rows.extend(data)
            return mock_table

        mock_db.create_table.side_effect = _capture_create

        with patch("lex_cases.indexer.lancedb.connect", return_value=mock_db), \
             patch("lex_cases.indexer.get_embedding_provider", return_value=_MockEmbedder()), \
             patch("lex_cases.indexer.os.makedirs"):
            index_cases([self._make_case()])

        assert captured_rows, "No rows were created"
        row = captured_rows[0]
        required_fields = {"id", "court", "az", "date", "type", "chunk_type", "text", "laws_cited", "url", "vector"}
        assert required_fields.issubset(row.keys()), f"Missing fields: {required_fields - row.keys()}"

    def test_id_field_is_sha1_hex(self):
        from lex_cases.indexer import index_cases

        captured_rows: list[dict] = []

        class _MockEmbedder:
            def embed(self, texts):
                return [[0.0] * 4 for _ in texts]

        mock_db = MagicMock()
        mock_db.table_names.return_value = []

        def _capture(name, data):
            captured_rows.extend(data)
            return MagicMock()

        mock_db.create_table.side_effect = _capture

        with patch("lex_cases.indexer.lancedb.connect", return_value=mock_db), \
             patch("lex_cases.indexer.get_embedding_provider", return_value=_MockEmbedder()), \
             patch("lex_cases.indexer.os.makedirs"):
            index_cases([self._make_case()])

        row = captured_rows[0]
        assert len(row["id"]) == 40
        assert all(c in "0123456789abcdef" for c in row["id"])

    def test_vector_field_is_list(self):
        from lex_cases.indexer import index_cases

        captured_rows: list[dict] = []

        class _MockEmbedder:
            def embed(self, texts):
                return [[1.0, 2.0, 3.0] for _ in texts]

        mock_db = MagicMock()
        mock_db.table_names.return_value = []

        def _capture(name, data):
            captured_rows.extend(data)
            return MagicMock()

        mock_db.create_table.side_effect = _capture

        with patch("lex_cases.indexer.lancedb.connect", return_value=mock_db), \
             patch("lex_cases.indexer.get_embedding_provider", return_value=_MockEmbedder()), \
             patch("lex_cases.indexer.os.makedirs"):
            index_cases([self._make_case()])

        assert isinstance(captured_rows[0]["vector"], list)


class TestIndexCasesBatching:
    """Verify that embedding calls are batched in groups of ≤ _BATCH_SIZE (16)."""

    def _make_cases(self, n: int) -> list[dict]:
        return [
            {
                "court": "BGH",
                "az": f"IV ZR {i}/24",
                "date": "2024-01-15",
                "type": "Urteil",
                "chunk_type": "leitsatz",
                "text": f"Entscheidung {i}",
                "laws_cited": [],
                "url": f"https://example.com/{i}",
            }
            for i in range(n)
        ]

    def test_single_batch_for_small_input(self):
        from lex_cases.indexer import index_cases

        embed_calls: list[list[str]] = []

        class _MockEmbedder:
            def embed(self, texts):
                embed_calls.append(list(texts))
                return [[0.0] * 4 for _ in texts]

        mock_db = MagicMock()
        mock_db.table_names.return_value = []
        mock_db.create_table.return_value = MagicMock()

        with patch("lex_cases.indexer.lancedb.connect", return_value=mock_db), \
             patch("lex_cases.indexer.get_embedding_provider", return_value=_MockEmbedder()), \
             patch("lex_cases.indexer.os.makedirs"):
            index_cases(self._make_cases(10))

        assert len(embed_calls) == 1
        assert len(embed_calls[0]) == 10

    def test_batches_exactly_at_limit(self):
        from lex_cases.indexer import _BATCH_SIZE, index_cases

        embed_calls: list[int] = []

        class _MockEmbedder:
            def embed(self, texts):
                embed_calls.append(len(texts))
                return [[0.0] * 4 for _ in texts]

        mock_db = MagicMock()
        mock_db.table_names.return_value = []
        mock_db.create_table.return_value = MagicMock()

        with patch("lex_cases.indexer.lancedb.connect", return_value=mock_db), \
             patch("lex_cases.indexer.get_embedding_provider", return_value=_MockEmbedder()), \
             patch("lex_cases.indexer.os.makedirs"):
            index_cases(self._make_cases(_BATCH_SIZE))

        assert len(embed_calls) == 1
        assert embed_calls[0] == _BATCH_SIZE

    def test_two_batches_for_input_larger_than_batch_size(self):
        from lex_cases.indexer import _BATCH_SIZE, index_cases

        embed_calls: list[int] = []

        class _MockEmbedder:
            def embed(self, texts):
                embed_calls.append(len(texts))
                return [[0.0] * 4 for _ in texts]

        mock_db = MagicMock()
        mock_db.table_names.return_value = []
        mock_db.create_table.return_value = MagicMock()

        n = _BATCH_SIZE + 5
        with patch("lex_cases.indexer.lancedb.connect", return_value=mock_db), \
             patch("lex_cases.indexer.get_embedding_provider", return_value=_MockEmbedder()), \
             patch("lex_cases.indexer.os.makedirs"):
            index_cases(self._make_cases(n))

        assert len(embed_calls) == 2
        assert all(bs <= _BATCH_SIZE for bs in embed_calls)
        assert sum(embed_calls) == n

    def test_no_batch_exceeds_batch_size(self):
        from lex_cases.indexer import _BATCH_SIZE, index_cases

        embed_calls: list[int] = []

        class _MockEmbedder:
            def embed(self, texts):
                embed_calls.append(len(texts))
                return [[0.0] * 4 for _ in texts]

        mock_db = MagicMock()
        mock_db.table_names.return_value = []
        mock_db.create_table.return_value = MagicMock()

        with patch("lex_cases.indexer.lancedb.connect", return_value=mock_db), \
             patch("lex_cases.indexer.get_embedding_provider", return_value=_MockEmbedder()), \
             patch("lex_cases.indexer.os.makedirs"):
            index_cases(self._make_cases(50))

        assert embed_calls, "embed was never called"
        assert all(bs <= _BATCH_SIZE for bs in embed_calls), \
            f"Batch size exceeded {_BATCH_SIZE}: {embed_calls}"


class TestIndexCasesSkipExisting:
    def test_skips_already_indexed_ids(self):
        from lex_cases.indexer import index_cases, make_case_id

        case = {
            "court": "BGH", "az": "IV ZR 1/24", "date": "2024-01-15",
            "type": "Urteil", "chunk_type": "leitsatz",
            "text": "text", "laws_cited": [], "url": "https://example.com/1",
        }
        existing_id = make_case_id("BGH", "IV ZR 1/24", 0)

        class _MockEmbedder:
            def embed(self, texts):
                return [[0.0] * 4 for _ in texts]

        mock_table = MagicMock()
        mock_table.search.return_value.select.return_value.to_list.return_value = [{"id": existing_id}]

        mock_db = MagicMock()
        mock_db.table_names.return_value = ["german_cases"]
        mock_db.open_table.return_value = mock_table

        with patch("lex_cases.indexer.lancedb.connect", return_value=mock_db), \
             patch("lex_cases.indexer.get_embedding_provider", return_value=_MockEmbedder()), \
             patch("lex_cases.indexer.os.makedirs"):
            result = index_cases([case])

        assert result == 0

    def test_empty_input_returns_zero(self):
        from lex_cases.indexer import index_cases
        assert index_cases([]) == 0
