"""Tests for rechtsprechung-im-internet.de provider."""

import io
import os
import zipfile
from unittest.mock import MagicMock, call, patch

import pytest

from lex_cases.providers.base import CaseProvider
from lex_cases.providers.rechtsprechung_im_internet import (
    RechtsprechungImInternetProvider,
    _COURT_CATALOG,
    _parse_xml_file,
    fetch_court_via_rss,
)

# Minimal case XML matching the rechtsprechung-im-internet.de format.
SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<dokument>
  <doknr>KORE123456789</doknr>
  <gericht>Bundesgerichtshof</gericht>
  <entscheidungsdatum>2024-01-15</entscheidungsdatum>
  <aktenzeichen>II ZR 123/23</aktenzeichen>
  <dokumenttyp>Urteil</dokumenttyp>
  <normkette>§ 280 BGB § 123 HGB</normkette>
  <leitsatz>Der Schuldner hat Schadensersatz zu leisten.</leitsatz>
  <tenor>Die Revision wird zurueckgewiesen.</tenor>
</dokument>
""".encode("utf-8")

SAMPLE_XML_NO_DOKNR = """<?xml version="1.0" encoding="UTF-8"?>
<dokument>
  <gericht>Bundesgerichtshof</gericht>
  <entscheidungsdatum>2024-02-20</entscheidungsdatum>
  <aktenzeichen>IV ZR 99/22</aktenzeichen>
  <dokumenttyp>Beschluss</dokumenttyp>
  <normkette></normkette>
  <leitsatz>Leitsatz ohne doknr.</leitsatz>
</dokument>
""".encode("utf-8")

SAMPLE_XML_NAMESPACED = """<?xml version="1.0" encoding="UTF-8"?>
<ns:dokument xmlns:ns="http://www.juris.de/jportal/ns/rechtsprechung/1.0">
  <ns:doknr>NSTEST001</ns:doknr>
  <ns:gericht>Bundesfinanzhof</ns:gericht>
  <ns:entscheidungsdatum>2023-11-01</ns:entscheidungsdatum>
  <ns:aktenzeichen>VIII R 1/23</ns:aktenzeichen>
  <ns:dokumenttyp>Urteil</ns:dokumenttyp>
  <ns:normkette>§ 15 EStG</ns:normkette>
  <ns:leitsatz>Leitsatz mit Namespace.</ns:leitsatz>
  <ns:tenor>Tenor mit Namespace.</ns:tenor>
</ns:dokument>
""".encode("utf-8")

# Minimal RSS feed XML returning one item with doc ID jb-KORE123456789.
SAMPLE_RSS = b"""<?xml version='1.0' encoding='UTF-8'?>
<rss version='2.0'>
<channel>
  <title>BGH-Rechtsprechung</title>
  <item>
    <title>BGH 2. Zivilsenat, Urteil vom 2024-01-15, II ZR 123/23</title>
    <link>https://www.rechtsprechung-im-internet.de/jportal/portal/page/bsjrsprod?doc.id=jb-KORE123456789</link>
    <pubDate>15 Jan 2024 12:00:00 +0100</pubDate>
    <guid isPermaLink="false">jb-KORE123456789</guid>
  </item>
</channel>
</rss>
"""


def _make_zip(*xml_pairs: tuple[str, bytes]) -> bytes:
    """Build an in-memory ZIP containing the given (filename, content) pairs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in xml_pairs:
            zf.writestr(name, data)
    return buf.getvalue()


def _rss_then_zip_mock(rss_bytes: bytes, zip_bytes: bytes):
    """Return a mock requests.get that serves RSS on the first call, ZIP on subsequent calls."""
    rss_response = MagicMock()
    rss_response.content = rss_bytes
    rss_response.raise_for_status = MagicMock()

    zip_response = MagicMock()
    zip_response.content = zip_bytes
    zip_response.raise_for_status = MagicMock()

    mock_get = MagicMock(side_effect=[rss_response, zip_response])
    return mock_get


class TestParseXmlFile:
    def test_returns_leitsatz_and_tenor_chunks(self):
        chunks = _parse_xml_file(SAMPLE_XML, "test.xml")
        assert len(chunks) == 2
        types = {c["chunk_type"] for c in chunks}
        assert types == {"leitsatz", "tenor"}

    def test_metadata_fields_populated(self):
        chunks = _parse_xml_file(SAMPLE_XML, "test.xml")
        for chunk in chunks:
            assert chunk["court"] == "Bundesgerichtshof"
            assert chunk["date"] == "2024-01-15"
            assert chunk["az"] == "II ZR 123/23"
            assert chunk["type"] == "Urteil"
            assert chunk["url"] == "https://www.rechtsprechung-im-internet.de/jportal/?docid=KORE123456789"

    def test_laws_cited_populated(self):
        chunks = _parse_xml_file(SAMPLE_XML, "test.xml")
        for chunk in chunks:
            assert isinstance(chunk["laws_cited"], list)
            assert len(chunk["laws_cited"]) > 0

    def test_leitsatz_text(self):
        chunks = _parse_xml_file(SAMPLE_XML, "test.xml")
        leitsatz = next(c for c in chunks if c["chunk_type"] == "leitsatz")
        assert "Schadensersatz" in leitsatz["text"]

    def test_tenor_text(self):
        chunks = _parse_xml_file(SAMPLE_XML, "test.xml")
        tenor = next(c for c in chunks if c["chunk_type"] == "tenor")
        assert "Revision" in tenor["text"]

    def test_fallback_docid_from_filename(self):
        chunks = _parse_xml_file(SAMPLE_XML_NO_DOKNR, "MYCHUNK.xml")
        assert len(chunks) == 1  # only leitsatz, no tenor
        assert "MYCHUNK" in chunks[0]["url"]

    def test_only_leitsatz_when_no_tenor(self):
        chunks = _parse_xml_file(SAMPLE_XML_NO_DOKNR, "doc.xml")
        chunk_types = [c["chunk_type"] for c in chunks]
        assert "leitsatz" in chunk_types
        assert "tenor" not in chunk_types

    def test_empty_laws_cited_when_no_normkette(self):
        chunks = _parse_xml_file(SAMPLE_XML_NO_DOKNR, "doc.xml")
        assert chunks[0]["laws_cited"] == []

    def test_invalid_xml_returns_empty(self):
        result = _parse_xml_file(b"not xml at all <<<", "bad.xml")
        assert result == []

    def test_namespaced_xml_parsed(self):
        chunks = _parse_xml_file(SAMPLE_XML_NAMESPACED, "ns.xml")
        assert len(chunks) == 2
        assert chunks[0]["court"] == "Bundesfinanzhof"
        assert chunks[0]["url"].endswith("NSTEST001")


class TestFetchCourtViaRss:
    def test_unsupported_court_raises(self):
        with pytest.raises(ValueError, match="not in catalog"):
            fetch_court_via_rss("UNKNOWN")

    def test_fetches_rss_then_individual_zips(self):
        zip_bytes = _make_zip(("case.xml", SAMPLE_XML))
        mock_get = _rss_then_zip_mock(SAMPLE_RSS, zip_bytes)

        with patch("lex_cases.providers.rechtsprechung_im_internet.requests.get", mock_get):
            chunks = fetch_court_via_rss("BGH")

        assert len(chunks) == 2
        # First call must be the RSS feed URL
        rss_url = mock_get.call_args_list[0][0][0]
        assert "feed" in rss_url and "bgh" in rss_url
        # Second call must be the per-case ZIP URL with the doc ID from the feed
        zip_url = mock_get.call_args_list[1][0][0]
        assert "bsjrs" in zip_url and "jb-KORE123456789" in zip_url

    def test_all_catalog_courts_accepted(self):
        zip_bytes = _make_zip(("case.xml", SAMPLE_XML))
        for court in _COURT_CATALOG:
            mock_get = _rss_then_zip_mock(SAMPLE_RSS, zip_bytes)
            with patch("lex_cases.providers.rechtsprechung_im_internet.requests.get", mock_get):
                chunks = fetch_court_via_rss(court)
                assert isinstance(chunks, list)

    def test_returns_parsed_chunks(self):
        zip_bytes = _make_zip(("decision.xml", SAMPLE_XML))
        mock_get = _rss_then_zip_mock(SAMPLE_RSS, zip_bytes)

        with patch("lex_cases.providers.rechtsprechung_im_internet.requests.get", mock_get):
            chunks = fetch_court_via_rss("BGH")

        assert len(chunks) == 2

    def test_skips_failed_case_downloads(self):
        import requests as req

        rss_response = MagicMock()
        rss_response.content = SAMPLE_RSS
        rss_response.raise_for_status = MagicMock()

        zip_response = MagicMock()
        zip_response.raise_for_status.side_effect = req.exceptions.HTTPError("404")

        mock_get = MagicMock(side_effect=[rss_response, zip_response])
        with patch("lex_cases.providers.rechtsprechung_im_internet.requests.get", mock_get):
            chunks = fetch_court_via_rss("BGH")

        assert chunks == []

    def test_skips_non_xml_files_in_zip(self):
        zip_bytes = _make_zip(("readme.txt", b"ignore me"), ("case.xml", SAMPLE_XML))
        mock_get = _rss_then_zip_mock(SAMPLE_RSS, zip_bytes)

        with patch("lex_cases.providers.rechtsprechung_im_internet.requests.get", mock_get):
            chunks = fetch_court_via_rss("BAG")

        assert len(chunks) == 2  # only from case.xml

    def test_rss_http_error_propagates(self):
        import requests as req

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError("503 Server Error")

        with patch("lex_cases.providers.rechtsprechung_im_internet.requests.get",
                   return_value=mock_response):
            with pytest.raises(req.exceptions.HTTPError, match="503"):
                fetch_court_via_rss("BFH")

    def test_empty_rss_feed_returns_empty_list(self):
        empty_rss = b"""<?xml version='1.0' encoding='UTF-8'?>
<rss version='2.0'><channel><title>BGH</title></channel></rss>"""

        rss_response = MagicMock()
        rss_response.content = empty_rss
        rss_response.raise_for_status = MagicMock()

        with patch("lex_cases.providers.rechtsprechung_im_internet.requests.get",
                   return_value=rss_response):
            chunks = fetch_court_via_rss("BGH")

        assert chunks == []


class TestRechtsprechungImInternetProvider:
    def test_inherits_case_provider(self):
        p = RechtsprechungImInternetProvider()
        assert isinstance(p, CaseProvider)

    def test_name(self):
        p = RechtsprechungImInternetProvider()
        assert p.name == "rechtsprechung-im-internet"

    def test_supported_courts_contains_all_six(self):
        p = RechtsprechungImInternetProvider()
        for court in ("BGH", "BVERFG", "BAG", "BFH", "BVERWG", "BPATG"):
            assert court in p.supported_courts

    def test_fetch_court_uses_rss_approach(self):
        p = RechtsprechungImInternetProvider()
        zip_bytes = _make_zip(("c.xml", SAMPLE_XML))
        mock_get = _rss_then_zip_mock(SAMPLE_RSS, zip_bytes)

        with patch("lex_cases.providers.rechtsprechung_im_internet.requests.get", mock_get):
            chunks = p.fetch_court("BGH")

        assert len(chunks) == 2
        assert all("court" in c for c in chunks)

    def test_fetch_court_result_has_required_keys(self):
        p = RechtsprechungImInternetProvider()
        zip_bytes = _make_zip(("c.xml", SAMPLE_XML))
        mock_get = _rss_then_zip_mock(SAMPLE_RSS, zip_bytes)

        with patch("lex_cases.providers.rechtsprechung_im_internet.requests.get", mock_get):
            chunks = p.fetch_court("BVERFG")

        required = {"court", "date", "az", "type", "text", "chunk_type", "laws_cited", "url"}
        for chunk in chunks:
            assert required.issubset(chunk.keys())


class TestFixtureFile:
    """Parse a real fixture XML file from tests/fixtures/bgh_sample.xml."""

    def _fixture_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), "fixtures", "bgh_sample.xml")

    def test_fixture_file_exists(self):
        assert os.path.exists(self._fixture_path())

    def test_parse_fixture_extracts_required_fields(self):
        with open(self._fixture_path(), "rb") as f:
            xml_bytes = f.read()
        chunks = _parse_xml_file(xml_bytes, "bgh_sample.xml")
        assert chunks, "Expected at least one chunk from fixture"
        for chunk in chunks:
            assert chunk.get("court"), "court is missing or empty"
            assert chunk.get("date"), "date is missing or empty"
            assert chunk.get("az"), "az is missing or empty"
            assert chunk.get("type"), "type is missing or empty"
            assert chunk.get("text"), "text is missing or empty"
            assert "laws_cited" in chunk

    def test_fixture_court_is_bgh(self):
        with open(self._fixture_path(), "rb") as f:
            xml_bytes = f.read()
        chunks = _parse_xml_file(xml_bytes, "bgh_sample.xml")
        assert chunks
        assert chunks[0]["court"] == "Bundesgerichtshof"

    def test_fixture_laws_cited_populated(self):
        with open(self._fixture_path(), "rb") as f:
            xml_bytes = f.read()
        chunks = _parse_xml_file(xml_bytes, "bgh_sample.xml")
        all_laws = [law for c in chunks for law in c.get("laws_cited", [])]
        assert all_laws, "Expected at least one law cited from fixture"
