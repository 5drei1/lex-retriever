"""Tests for the lex_cases CLI (python -m lex_cases)."""

import sys
from unittest.mock import MagicMock, patch

import pytest


class TestCLIHelp:
    def test_no_args_shows_subcommands(self, capsys):
        with patch.object(sys, "argv", ["lex_cases"]):
            from lex_cases.__main__ import main
            main()
        out = capsys.readouterr().out
        assert "index" in out
        assert "search" in out
        assert "status" in out

    def test_index_help(self, capsys):
        with patch.object(sys, "argv", ["lex_cases", "index", "--help"]):
            from lex_cases.__main__ import main
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "COURT" in out

    def test_search_help(self, capsys):
        with patch.object(sys, "argv", ["lex_cases", "search", "--help"]):
            from lex_cases.__main__ import main
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "QUERY" in out
        assert "--court" in out
        assert "--laws" in out
        assert "--top-k" in out


class TestCLIIndex:
    def test_index_calls_index_court(self):
        with patch("lex_cases.indexer.index_court", return_value=42) as mock_ic:
            with patch.object(sys, "argv", ["lex_cases", "index", "BGH"]):
                from lex_cases.__main__ import main
                main()
        mock_ic.assert_called_once_with("BGH")

    def test_index_uppercases_court(self):
        with patch("lex_cases.indexer.index_court", return_value=5) as mock_ic:
            with patch.object(sys, "argv", ["lex_cases", "index", "bgh"]):
                from lex_cases.__main__ import main
                main()
        mock_ic.assert_called_once_with("BGH")

    def test_index_already_done_message(self, capsys):
        with patch("lex_cases.indexer.index_court", return_value=0):
            with patch.object(sys, "argv", ["lex_cases", "index", "BAG"]):
                from lex_cases.__main__ import main
                main()
        assert "already up to date" in capsys.readouterr().out

    def test_index_shows_count(self, capsys):
        with patch("lex_cases.indexer.index_court", return_value=100):
            with patch.object(sys, "argv", ["lex_cases", "index", "BGH"]):
                from lex_cases.__main__ import main
                main()
        assert "100" in capsys.readouterr().out


class TestCLIIndexAll:
    def test_index_all_calls_index_all_courts(self):
        fake = {"BGH": 10, "BAG": 5}
        with patch("lex_cases.indexer.index_all_courts", return_value=fake) as mock_all:
            with patch.object(sys, "argv", ["lex_cases", "index-all"]):
                from lex_cases.__main__ import main
                main()
        mock_all.assert_called_once_with()

    def test_index_all_prints_per_court(self, capsys):
        fake = {"BGH": 200, "BVERFG": 0}
        with patch("lex_cases.indexer.index_all_courts", return_value=fake):
            with patch.object(sys, "argv", ["lex_cases", "index-all"]):
                from lex_cases.__main__ import main
                main()
        out = capsys.readouterr().out
        assert "BGH" in out
        assert "200" in out
        assert "BVERFG" in out


class TestCLIStatus:
    def test_status_shows_per_court_counts(self, capsys):
        # DB stores full court names as parsed from XML
        fake_counts = {"Bundesgerichtshof": 150, "Bundesarbeitsgericht": 80}
        with patch("lex_cases.indexer.get_court_counts", return_value=fake_counts), \
             patch("lex_cases.indexer.LANCE_PATH", "/fake/lancedb"):
            with patch.object(sys, "argv", ["lex_cases", "status"]):
                from lex_cases.__main__ import main
                main()
        out = capsys.readouterr().out
        assert "150" in out
        assert "80" in out
        assert "BGH" in out
        assert "BAG" in out

    def test_status_empty_index_message(self, capsys):
        with patch("lex_cases.indexer.get_court_counts", return_value={}), \
             patch("lex_cases.indexer.LANCE_PATH", "/fake/lancedb"):
            with patch.object(sys, "argv", ["lex_cases", "status"]):
                from lex_cases.__main__ import main
                main()
        out = capsys.readouterr().out
        assert "empty" in out.lower() or "index-all" in out


class TestCLISearch:
    def _mock_results(self):
        return [
            {
                "court": "Bundesgerichtshof",
                "az": "VI ZR 123/23",
                "date": "2024-03-15",
                "type": "Urteil",
                "laws_cited": ["§ 823 BGB"],
                "url": "https://example.com/decision/1",
                "text": "Der Hersteller haftet für Produktfehler.",
                "score": 0.91,
            }
        ]

    def test_search_calls_retriever(self):
        mock_retriever = MagicMock()
        mock_retriever.search.return_value = self._mock_results()
        with patch("lex_cases.retriever.LexCaseRetriever", return_value=mock_retriever):
            with patch.object(sys, "argv", ["lex_cases", "search", "Produzentenhaftung"]):
                from lex_cases.__main__ import main
                main()
        mock_retriever.search.assert_called_once_with(
            "Produzentenhaftung",
            courts=None,
            laws_cited=None,
            top_k=10,
        )

    def test_search_with_court_filter(self):
        mock_retriever = MagicMock()
        mock_retriever.search.return_value = self._mock_results()
        with patch("lex_cases.retriever.LexCaseRetriever", return_value=mock_retriever):
            with patch.object(sys, "argv", ["lex_cases", "search", "Haftung", "-c", "BGH"]):
                from lex_cases.__main__ import main
                main()
        mock_retriever.search.assert_called_once_with(
            "Haftung",
            courts=["BGH"],
            laws_cited=None,
            top_k=10,
        )

    def test_search_with_top_k(self):
        mock_retriever = MagicMock()
        mock_retriever.search.return_value = self._mock_results()
        with patch("lex_cases.retriever.LexCaseRetriever", return_value=mock_retriever):
            with patch.object(sys, "argv", ["lex_cases", "search", "Vertrag", "-k", "5"]):
                from lex_cases.__main__ import main
                main()
        mock_retriever.search.assert_called_once_with(
            "Vertrag",
            courts=None,
            laws_cited=None,
            top_k=5,
        )

    def test_search_prints_results(self, capsys):
        mock_retriever = MagicMock()
        mock_retriever.search.return_value = self._mock_results()
        with patch("lex_cases.retriever.LexCaseRetriever", return_value=mock_retriever):
            with patch.object(sys, "argv", ["lex_cases", "search", "Produzentenhaftung"]):
                from lex_cases.__main__ import main
                main()
        out = capsys.readouterr().out
        assert "VI ZR 123/23" in out
        assert "§ 823 BGB" in out
        assert "0.910" in out

    def test_search_no_results_message(self, capsys):
        mock_retriever = MagicMock()
        mock_retriever.search.return_value = []
        with patch("lex_cases.retriever.LexCaseRetriever", return_value=mock_retriever):
            with patch.object(sys, "argv", ["lex_cases", "search", "xyz123"]):
                from lex_cases.__main__ import main
                main()
        assert "No results" in capsys.readouterr().out

    def test_search_exception_exits_nonzero(self):
        mock_retriever = MagicMock()
        mock_retriever.search.side_effect = RuntimeError("table not found")
        with patch("lex_cases.retriever.LexCaseRetriever", return_value=mock_retriever):
            with patch.object(sys, "argv", ["lex_cases", "search", "Haftung"]):
                from lex_cases.__main__ import main
                with pytest.raises(SystemExit) as exc:
                    main()
            assert exc.value.code != 0
