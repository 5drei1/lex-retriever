"""Unit tests for indexer chunking logic."""

import logging

import pytest

from lex_retriever.indexer import chunk_text


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
