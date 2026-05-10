"""Tests for lex_cases.providers.rechtsprechung_im_internet using fixture files."""

from __future__ import annotations

import io
import os
import zipfile
from unittest.mock import MagicMock, patch

import pytest
import requests

from lex_cases.providers.rechtsprechung_im_internet import (
    _COURT_CATALOG,
    _fetch_rss_doc_ids,
    _parse_xml_file,
    fetch_court_via_rss,
)

_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(filename: str) -> bytes:
    with open(os.path.join(_FIXTURES_DIR, filename), "rb") as f:
        return f.read()


def _make_zip_from_fixture(filename: str) -> bytes:
    data = _load_fixture(filename)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(filename, data)
    return buf.getvalue()


class TestCourtCatalog:
    def test_contains_all_six_courts(self):
        for court in ("BGH", "BVERFG", "BAG", "BFH", "BVERWG", "BPATG"):
            assert court in _COURT_CATALOG, f"{court} not in _COURT_CATALOG"

    def test_each_entry_has_name_and_slug(self):
        for code, entry in _COURT_CATALOG.items():
            assert len(entry) == 2, f"{code}: expected (name, slug) tuple"
            name, slug = entry
            assert name, f"{code}: court name is empty"
            assert slug, f"{code}: slug is empty"

    def test_slugs_are_lowercase(self):
        for code, (_, slug) in _COURT_CATALOG.items():
            assert slug == slug.lower(), f"{code}: slug '{slug}' is not lowercase"


class TestParseXmlFileWithFixture:
    """Parse the `tests/fixtures/bgh_sample.xml` fixture file through `_parse_xml_file`."""

    def test_fixture_file_exists(self):
        assert os.path.exists(os.path.join(_FIXTURES_DIR, "bgh_sample.xml"))

    def test_yields_leitsatz_and_tenor_chunks(self):
        xml_bytes = _load_fixture("bgh_sample.xml")
        chunks = _parse_xml_file(xml_bytes, "bgh_sample.xml")
        chunk_types = {c["chunk_type"] for c in chunks}
        assert "leitsatz" in chunk_types
        assert "tenor" in chunk_types

    def test_court_field_extracted(self):
        xml_bytes = _load_fixture("bgh_sample.xml")
        chunks = _parse_xml_file(xml_bytes, "bgh_sample.xml")
        assert chunks
        assert chunks[0]["court"] == "Bundesgerichtshof"

    def test_date_field_extracted(self):
        xml_bytes = _load_fixture("bgh_sample.xml")
        chunks = _parse_xml_file(xml_bytes, "bgh_sample.xml")
        assert chunks[0]["date"] == "2024-03-15"

    def test_az_field_extracted(self):
        xml_bytes = _load_fixture("bgh_sample.xml")
        chunks = _parse_xml_file(xml_bytes, "bgh_sample.xml")
        assert chunks[0]["az"] == "VI ZR 123/23"

    def test_type_field_extracted(self):
        xml_bytes = _load_fixture("bgh_sample.xml")
        chunks = _parse_xml_file(xml_bytes, "bgh_sample.xml")
        assert chunks[0]["type"] == "Urteil"

    def test_url_field_contains_doknr(self):
        xml_bytes = _load_fixture("bgh_sample.xml")
        chunks = _parse_xml_file(xml_bytes, "bgh_sample.xml")
        assert "KORE300042024" in chunks[0]["url"]

    def test_laws_cited_is_list(self):
        xml_bytes = _load_fixture("bgh_sample.xml")
        chunks = _parse_xml_file(xml_bytes, "bgh_sample.xml")
        for chunk in chunks:
            assert isinstance(chunk["laws_cited"], list)

    def test_laws_cited_nonempty(self):
        xml_bytes = _load_fixture("bgh_sample.xml")
        chunks = _parse_xml_file(xml_bytes, "bgh_sample.xml")
        assert any(len(c["laws_cited"]) > 0 for c in chunks)

    def test_leitsatz_text_nonempty(self):
        xml_bytes = _load_fixture("bgh_sample.xml")
        chunks = _parse_xml_file(xml_bytes, "bgh_sample.xml")
        leitsatz = next(c for c in chunks if c["chunk_type"] == "leitsatz")
        assert leitsatz["text"].strip()

    def test_tenor_text_nonempty(self):
        xml_bytes = _load_fixture("bgh_sample.xml")
        chunks = _parse_xml_file(xml_bytes, "bgh_sample.xml")
        tenor = next(c for c in chunks if c["chunk_type"] == "tenor")
        assert tenor["text"].strip()

    def test_all_required_fields_present(self):
        xml_bytes = _load_fixture("bgh_sample.xml")
        chunks = _parse_xml_file(xml_bytes, "bgh_sample.xml")
        required = {"court", "date", "az", "type", "text", "chunk_type", "laws_cited", "url"}
        for chunk in chunks:
            assert required.issubset(chunk.keys()), f"Missing: {required - chunk.keys()}"


_SAMPLE_RSS = b"""<?xml version='1.0' encoding='UTF-8'?>
<rss version='2.0'>
<channel>
  <title>BGH-Rechtsprechung</title>
  <item>
    <title>BGH, Urteil 2024-03-15, VI ZR 123/23</title>
    <guid isPermaLink="false">jb-KORE300042024</guid>
  </item>
</channel>
</rss>
"""


class TestFetchRssRetry:
    """Verify that _fetch_rss_doc_ids retries on transient network errors."""

    def _rss_response(self) -> MagicMock:
        resp = MagicMock()
        resp.content = _SAMPLE_RSS
        resp.raise_for_status = MagicMock()
        return resp

    def test_retries_twice_then_succeeds(self):
        call_count = 0

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests.exceptions.ConnectionError("transient error")
            return self._rss_response()

        with patch("lex_cases.providers.rechtsprechung_im_internet.requests.get",
                   side_effect=_side_effect), \
             patch("time.sleep"):
            doc_ids = _fetch_rss_doc_ids("bgh")

        assert call_count == 3
        assert doc_ids == ["jb-KORE300042024"]

    def test_fails_after_three_consecutive_errors(self):
        with patch("lex_cases.providers.rechtsprechung_im_internet.requests.get",
                   side_effect=requests.exceptions.ConnectionError("always fails")), \
             patch("time.sleep"):
            with pytest.raises(requests.exceptions.ConnectionError):
                _fetch_rss_doc_ids("bgh")

    def test_first_attempt_success_no_retry(self):
        with patch("lex_cases.providers.rechtsprechung_im_internet.requests.get",
                   return_value=self._rss_response()) as mock_get:
            doc_ids = _fetch_rss_doc_ids("bgh")

        assert mock_get.call_count == 1
        assert "jb-KORE300042024" in doc_ids
