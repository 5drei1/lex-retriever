"""Tests for CellarProvider."""

import pytest
from unittest.mock import patch, MagicMock

from lex_retriever.providers.cellar_provider import (
    CellarProvider,
    _parse_cellar_html,
    _resolve_cellar_uri,
    _fallback_url,
)
from lex_retriever.providers import REGISTRY, all_supported_laws, get_providers_for_law


SAMPLE_XHTML = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<body>
<div class="eli-container">
  <div class="eli-subdivision" id="art_1">
    <p class="oj-doc-ti">Artikel 1 Gegenstand und Ziele</p>
    <p class="oj-normal">Diese Verordnung enthaelt Vorschriften zum Schutz natuerlicher Personen.</p>
  </div>
  <div class="eli-subdivision" id="art_5">
    <p class="oj-doc-ti">Artikel 5 Grundsaetze fuer die Verarbeitung</p>
    <p class="oj-normal">Personenbezogene Daten muessen rechtmaessig verarbeitet werden.</p>
  </div>
</div>
</body>
</html>"""

_MOCK_SPARQL_RESULT = {
    "results": {
        "bindings": [
            {"work": {"value": "http://publications.europa.eu/resource/cellar/test-uuid.0001.01"}}
        ]
    }
}


def _make_sparql_mock():
    mock_sparql = MagicMock()
    mock_sparql.query.return_value.convert.return_value = _MOCK_SPARQL_RESULT
    return mock_sparql


class TestCellarProvider:
    def test_name(self):
        p = CellarProvider()
        assert p.name == "cellar"

    def test_supported_laws_contains_dsgvo(self):
        p = CellarProvider()
        assert "DSGVO" in p.supported_laws

    def test_supported_laws_contains_nis2(self):
        p = CellarProvider()
        assert "NIS2" in p.supported_laws

    def test_is_available_dsgvo(self):
        p = CellarProvider()
        assert p.is_available("DSGVO")
        assert p.is_available("dsgvo")

    def test_is_not_available_bgb(self):
        p = CellarProvider()
        assert not p.is_available("BGB")

    def test_fetch_unsupported_raises(self):
        p = CellarProvider()
        with pytest.raises(ValueError, match="not supported"):
            p.fetch("UNKNOWNLAW")

    def test_fetch_uses_sparql_uri_when_available(self):
        p = CellarProvider()
        mock_response = MagicMock()
        mock_response.text = SAMPLE_XHTML
        mock_response.raise_for_status = MagicMock()

        with patch(
            "lex_retriever.providers.cellar_provider.SPARQLWrapper",
            return_value=_make_sparql_mock(),
        ):
            with patch(
                "lex_retriever.providers.cellar_provider.requests.get",
                return_value=mock_response,
            ) as mock_get:
                chunks = p.fetch("DSGVO")
                url_called = mock_get.call_args[0][0]
                assert "cellar" in url_called or "32016R0679" in url_called
                assert len(chunks) > 0

    def test_fetch_falls_back_to_eurlex_url_on_sparql_error(self):
        p = CellarProvider()
        mock_response = MagicMock()
        mock_response.text = SAMPLE_XHTML
        mock_response.raise_for_status = MagicMock()

        with patch(
            "lex_retriever.providers.cellar_provider.SPARQLWrapper",
            side_effect=Exception("network error"),
        ):
            with patch(
                "lex_retriever.providers.cellar_provider.requests.get",
                return_value=mock_response,
            ) as mock_get:
                chunks = p.fetch("DSGVO")
                url_called = mock_get.call_args[0][0]
                assert "32016R0679" in url_called
                assert "eur-lex.europa.eu" in url_called
                assert len(chunks) > 0

    def test_fetch_returns_chunks_with_required_keys(self):
        p = CellarProvider()
        mock_response = MagicMock()
        mock_response.text = SAMPLE_XHTML
        mock_response.raise_for_status = MagicMock()

        with patch(
            "lex_retriever.providers.cellar_provider.SPARQLWrapper",
            side_effect=Exception("timeout"),
        ):
            with patch(
                "lex_retriever.providers.cellar_provider.requests.get",
                return_value=mock_response,
            ):
                chunks = p.fetch("DSGVO")

        for chunk in chunks:
            assert "paragraph" in chunk
            assert "text" in chunk
            assert "source" in chunk
            assert chunk["text"]

    def test_fetch_source_is_celex_number(self):
        p = CellarProvider()
        mock_response = MagicMock()
        mock_response.text = SAMPLE_XHTML
        mock_response.raise_for_status = MagicMock()

        with patch(
            "lex_retriever.providers.cellar_provider.SPARQLWrapper",
            side_effect=Exception("timeout"),
        ):
            with patch(
                "lex_retriever.providers.cellar_provider.requests.get",
                return_value=mock_response,
            ):
                chunks = p.fetch("DSGVO")

        for chunk in chunks:
            assert chunk["source"] == "32016R0679"

    def test_available_laws_includes_dsgvo(self):
        p = CellarProvider()
        laws = p.available_laws()
        codes = [l["code"] for l in laws]
        assert "DSGVO" in codes

    def test_available_laws_has_url(self):
        p = CellarProvider()
        for law in p.available_laws():
            assert law["url"]
            assert "32016R0679" in law["url"] or law["code"] != "DSGVO"


class TestParseCellarHtml:
    def test_parses_articles(self):
        chunks = _parse_cellar_html(SAMPLE_XHTML, "32016R0679")
        assert len(chunks) == 2

    def test_article_numbers_extracted(self):
        chunks = _parse_cellar_html(SAMPLE_XHTML, "32016R0679")
        paragraphs = [c["paragraph"] for c in chunks]
        assert any("1" in p for p in paragraphs)
        assert any("5" in p for p in paragraphs)

    def test_source_is_celex(self):
        chunks = _parse_cellar_html(SAMPLE_XHTML, "32016R0679")
        for chunk in chunks:
            assert chunk["source"] == "32016R0679"

    def test_empty_html_returns_empty_list(self):
        chunks = _parse_cellar_html("<html><body></body></html>", "32016R0679")
        assert chunks == []

    def test_text_content_extracted(self):
        chunks = _parse_cellar_html(SAMPLE_XHTML, "32016R0679")
        texts = [c["text"] for c in chunks]
        assert any("personenbezogener" in t.lower() or "natuerlicher" in t for t in texts)

    def test_heading_included_in_paragraph(self):
        chunks = _parse_cellar_html(SAMPLE_XHTML, "32016R0679")
        paragraphs = [c["paragraph"] for c in chunks]
        assert any("Gegenstand" in p for p in paragraphs)


class TestResolveCellarUri:
    def test_returns_uri_on_success(self):
        with patch(
            "lex_retriever.providers.cellar_provider.SPARQLWrapper",
            return_value=_make_sparql_mock(),
        ):
            uri = _resolve_cellar_uri("32016R0679")
        assert uri == "http://publications.europa.eu/resource/cellar/test-uuid.0001.01"

    def test_returns_none_when_no_results(self):
        empty_result = {"results": {"bindings": []}}
        mock_sparql = MagicMock()
        mock_sparql.query.return_value.convert.return_value = empty_result
        with patch(
            "lex_retriever.providers.cellar_provider.SPARQLWrapper",
            return_value=mock_sparql,
        ):
            uri = _resolve_cellar_uri("NONEXISTENT")
        assert uri is None


class TestFallbackUrl:
    def test_contains_celex(self):
        url = _fallback_url("32016R0679")
        assert "32016R0679" in url
        assert "eur-lex.europa.eu" in url

    def test_german_language(self):
        url = _fallback_url("32016R0679")
        assert "/DE/" in url


class TestRegistryIntegration:
    def test_cellar_provider_in_registry(self):
        assert any(p.name == "cellar" for p in REGISTRY)

    def test_dsgvo_in_all_supported_laws(self):
        laws = all_supported_laws()
        assert "DSGVO" in laws

    def test_get_providers_for_dsgvo(self):
        providers = get_providers_for_law("DSGVO")
        assert len(providers) > 0
        assert any(p.name == "cellar" for p in providers)

    def test_nis2_supported(self):
        providers = get_providers_for_law("NIS2")
        assert any(p.name == "cellar" for p in providers)
