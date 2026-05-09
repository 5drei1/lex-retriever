"""Tests for EurLexProvider."""

import pytest
from unittest.mock import patch, MagicMock

from lex_retriever.providers.eur_lex import EurLexProvider, _parse_eur_lex_xml
from lex_retriever.providers import REGISTRY, all_supported_laws, get_providers_for_law


SAMPLE_AKN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0">
  <act>
    <body>
      <article eId="art-1">
        <num>1</num>
        <heading>Gegenstand und Ziele</heading>
        <content>
          <p>Diese Verordnung enthaelt Vorschriften zum Schutz natuerlicher Personen bei der Verarbeitung personenbezogener Daten.</p>
        </content>
      </article>
      <article eId="art-5">
        <num>5</num>
        <heading>Grundsaetze fuer die Verarbeitung personenbezogener Daten</heading>
        <content>
          <p>Personenbezogene Daten muessen auf rechtmaessige Weise verarbeitet werden.</p>
        </content>
      </article>
    </body>
  </act>
</akomaNtoso>""".encode("utf-8")


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
        mock_response.content = SAMPLE_AKN_XML
        mock_response.raise_for_status = MagicMock()

        with patch("lex_retriever.providers.eur_lex.requests.get", return_value=mock_response) as mock_get:
            chunks = p.fetch("DSGVO")
            assert mock_get.called
            url_called = mock_get.call_args[0][0]
            assert "32016R0679" in url_called
            assert len(chunks) > 0

    def test_fetch_returns_chunks_with_required_keys(self):
        p = EurLexProvider()
        mock_response = MagicMock()
        mock_response.content = SAMPLE_AKN_XML
        mock_response.raise_for_status = MagicMock()

        with patch("lex_retriever.providers.eur_lex.requests.get", return_value=mock_response):
            chunks = p.fetch("DSGVO")

        for chunk in chunks:
            assert "paragraph" in chunk
            assert "text" in chunk
            assert "source" in chunk
            assert chunk["text"]


class TestParseEurLexXml:
    def test_parses_akn_articles(self):
        chunks = _parse_eur_lex_xml(SAMPLE_AKN_XML, "DSGVO")
        assert len(chunks) == 2

    def test_article_numbers_extracted(self):
        chunks = _parse_eur_lex_xml(SAMPLE_AKN_XML, "DSGVO")
        paragraphs = [c["paragraph"] for c in chunks]
        assert any("1" in p for p in paragraphs)
        assert any("5" in p for p in paragraphs)

    def test_source_contains_celex(self):
        chunks = _parse_eur_lex_xml(SAMPLE_AKN_XML, "DSGVO")
        for chunk in chunks:
            assert "eur-lex" in chunk["source"]

    def test_empty_xml_returns_empty_list(self):
        chunks = _parse_eur_lex_xml(b"not valid xml <<<", "DSGVO")
        assert chunks == []

    def test_text_content_extracted(self):
        chunks = _parse_eur_lex_xml(SAMPLE_AKN_XML, "DSGVO")
        texts = [c["text"] for c in chunks]
        assert any("personenbezogener Daten" in t for t in texts) or any("personenbezogener" in t for t in texts)


class TestRegistryIntegration:
    def test_eur_lex_provider_in_registry(self):
        assert any(p.name == "eur-lex" for p in REGISTRY)

    def test_dsgvo_in_all_supported_laws(self):
        laws = all_supported_laws()
        assert "DSGVO" in laws

    def test_get_providers_for_dsgvo(self):
        providers = get_providers_for_law("DSGVO")
        assert len(providers) > 0
        assert any(p.name == "eur-lex" for p in providers)
