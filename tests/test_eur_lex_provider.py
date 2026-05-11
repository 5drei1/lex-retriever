"""Tests for EurLexProvider."""

import pytest
from unittest.mock import patch, MagicMock

from lex_retriever.providers.eur_lex import EurLexProvider, _parse_cellar_xhtml
from lex_retriever.providers import REGISTRY, all_supported_laws, get_providers_for_law


# Minimal XHTML matching the EU Publications Office ELI format
SAMPLE_CELLAR_XHTML = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<body>
<div class="eli-container">
  <div class="eli-subdivision" id="art_1">
    <p class="oj-doc-ti">Artikel 1 Gegenstand und Ziele</p>
    <p class="oj-normal">Diese Verordnung enthaelt Vorschriften zum Schutz natuerlicher Personen bei der Verarbeitung personenbezogener Daten.</p>
  </div>
  <div class="eli-subdivision" id="art_5">
    <p class="oj-doc-ti">Artikel 5 Grundsaetze fuer die Verarbeitung</p>
    <p class="oj-normal">Personenbezogene Daten muessen rechtmaessig verarbeitet werden.</p>
  </div>
</div>
</body>
</html>"""


class TestEurLexProvider:
    def test_name(self):
        p = EurLexProvider()
        assert p.name == "eur-lex"

    def test_supported_laws_contains_dsgvo(self):
        p = EurLexProvider()
        assert "DSGVO" in p.supported_laws

    def test_is_available_dsgvo(self):
        p = EurLexProvider()
        assert p.is_available("DSGVO")
        assert p.is_available("dsgvo")

    def test_is_not_available_bgb(self):
        p = EurLexProvider()
        assert not p.is_available("BGB")

    def test_fetch_unsupported_raises(self):
        p = EurLexProvider()
        with pytest.raises(ValueError, match="not supported"):
            p.fetch("UNKNOWNLAW")

    def test_fetch_calls_correct_url(self):
        p = EurLexProvider()
        mock_response = MagicMock()
        mock_response.text = SAMPLE_CELLAR_XHTML
        mock_response.raise_for_status = MagicMock()

        with patch("lex_retriever.providers.eur_lex.requests.get", return_value=mock_response) as mock_get:
            chunks = p.fetch("DSGVO")
            assert mock_get.called
            url_called = mock_get.call_args[0][0]
            assert "cellar" in url_called
            assert len(chunks) > 0

    def test_fetch_returns_chunks_with_required_keys(self):
        p = EurLexProvider()
        mock_response = MagicMock()
        mock_response.text = SAMPLE_CELLAR_XHTML
        mock_response.raise_for_status = MagicMock()

        with patch("lex_retriever.providers.eur_lex.requests.get", return_value=mock_response):
            chunks = p.fetch("DSGVO")

        for chunk in chunks:
            assert "paragraph" in chunk
            assert "text" in chunk
            assert "source" in chunk
            assert chunk["text"]


class TestParseCellarXhtml:
    def test_parses_eli_articles(self):
        chunks = _parse_cellar_xhtml(SAMPLE_CELLAR_XHTML, "DSGVO")
        assert len(chunks) == 2

    def test_article_numbers_extracted(self):
        chunks = _parse_cellar_xhtml(SAMPLE_CELLAR_XHTML, "DSGVO")
        paragraphs = [c["paragraph"] for c in chunks]
        assert any("1" in p for p in paragraphs)
        assert any("5" in p for p in paragraphs)

    def test_source_contains_eur_lex(self):
        chunks = _parse_cellar_xhtml(SAMPLE_CELLAR_XHTML, "DSGVO")
        for chunk in chunks:
            assert "eur-lex" in chunk["source"]

    def test_empty_html_returns_empty_list(self):
        chunks = _parse_cellar_xhtml("<html><body></body></html>", "DSGVO")
        assert chunks == []

    def test_text_content_extracted(self):
        chunks = _parse_cellar_xhtml(SAMPLE_CELLAR_XHTML, "DSGVO")
        texts = [c["text"] for c in chunks]
        assert any("personenbezogener" in t for t in texts)

    def test_heading_included_in_paragraph(self):
        chunks = _parse_cellar_xhtml(SAMPLE_CELLAR_XHTML, "DSGVO")
        paragraphs = [c["paragraph"] for c in chunks]
        assert any("Gegenstand" in p for p in paragraphs)


class TestRegistryIntegration:
    def test_cellar_provider_in_registry(self):
        # EurLexProvider replaced by CellarProvider in the registry
        assert any(p.name == "cellar" for p in REGISTRY)

    def test_dsgvo_in_all_supported_laws(self):
        laws = all_supported_laws()
        assert "DSGVO" in laws

    def test_get_providers_for_dsgvo(self):
        providers = get_providers_for_law("DSGVO")
        assert len(providers) > 0
        assert any(p.name == "cellar" for p in providers)
