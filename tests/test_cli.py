"""Tests for the CLI entrypoint (python -m lex_retriever)."""

import sys
import pytest
from io import StringIO
from unittest.mock import patch


class TestCLIListLaws:
    def test_list_laws_outputs_known_laws(self, capsys):
        with patch.object(sys, "argv", ["lex_retriever", "list-laws"]):
            from lex_retriever.__main__ import main
            main()

        captured = capsys.readouterr()
        assert "BGB" in captured.out
        assert "DSGVO" in captured.out
        assert "Available laws" in captured.out

    def test_list_laws_format(self, capsys):
        with patch.object(sys, "argv", ["lex_retriever", "list-laws"]):
            from lex_retriever.__main__ import main
            main()

        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        law_lines = [l for l in lines if l.startswith("  -")]
        assert len(law_lines) >= 5  # at least BGB, HGB, GmbHG, GewO, DSGVO


class TestCLIHelp:
    def test_no_args_shows_usage(self, capsys):
        with patch.object(sys, "argv", ["lex_retriever"]):
            from lex_retriever.__main__ import main
            main()

        captured = capsys.readouterr()
        assert "Usage" in captured.out
        assert "index-all" in captured.out
        assert "list-laws" in captured.out

    def test_unknown_command_shows_usage(self, capsys):
        with patch.object(sys, "argv", ["lex_retriever", "unknown-cmd"]):
            from lex_retriever.__main__ import main
            main()

        captured = capsys.readouterr()
        assert "Usage" in captured.out


class TestCLIIndex:
    def test_index_calls_index_law(self):
        with patch("lex_retriever.indexer.index_law", return_value=42) as mock_index:
            with patch.object(sys, "argv", ["lex_retriever", "index", "BGB"]):
                from lex_retriever.__main__ import main
                main()
            mock_index.assert_called_once_with("BGB", force=False)

    def test_index_with_force_flag(self):
        with patch("lex_retriever.indexer.index_law", return_value=42) as mock_index:
            with patch.object(sys, "argv", ["lex_retriever", "index", "BGB", "--force"]):
                from lex_retriever.__main__ import main
                main()
            mock_index.assert_called_once_with("BGB", force=True)

    def test_index_law_code_uppercased(self):
        with patch("lex_retriever.indexer.index_law", return_value=10) as mock_index:
            with patch.object(sys, "argv", ["lex_retriever", "index", "bgb"]):
                from lex_retriever.__main__ import main
                main()
            mock_index.assert_called_once_with("BGB", force=False)


class TestCLIIndexAll:
    def test_index_all_calls_index_all_laws(self):
        fake_results = {"BGB": 100, "DSGVO": 50}
        with patch("lex_retriever.indexer.index_all_laws", return_value=fake_results) as mock_all:
            with patch.object(sys, "argv", ["lex_retriever", "index-all"]):
                from lex_retriever.__main__ import main
                main()
            mock_all.assert_called_once_with(force=False)

    def test_index_all_with_force(self):
        fake_results = {"BGB": 100}
        with patch("lex_retriever.indexer.index_all_laws", return_value=fake_results) as mock_all:
            with patch.object(sys, "argv", ["lex_retriever", "index-all", "--force"]):
                from lex_retriever.__main__ import main
                main()
            mock_all.assert_called_once_with(force=True)

    def test_index_all_output_shows_results(self, capsys):
        fake_results = {"BGB": 500, "DSGVO": 99}
        with patch("lex_retriever.indexer.index_all_laws", return_value=fake_results):
            with patch.object(sys, "argv", ["lex_retriever", "index-all"]):
                from lex_retriever.__main__ import main
                main()

        captured = capsys.readouterr()
        assert "BGB" in captured.out
        assert "DSGVO" in captured.out
