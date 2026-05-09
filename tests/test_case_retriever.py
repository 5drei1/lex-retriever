"""Tests for LexCaseRetriever."""

from __future__ import annotations

import hashlib
import random
from unittest.mock import MagicMock, patch

import pytest


def _det_vector(text: str, dims: int = 384) -> list[float]:
    """Deterministic embedding vector derived from text hash."""
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**31)
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(dims)]


def _make_row(
    court="BGH",
    az="IV ZR 1/24",
    date="2024-01-15",
    type_="Urteil",
    leitsatz="Test-Leitsatz",
    laws_cited=None,
    url="https://www.rechtsprechung-im-internet.de/jportal/?docid=TEST001",
    distance=0.1,
) -> dict:
    return {
        "court": court,
        "az": az,
        "date": date,
        "type": type_,
        "leitsatz": leitsatz,
        "laws_cited": laws_cited if laws_cited is not None else [],
        "url": url,
        "vector": _det_vector(leitsatz),
        "_distance": distance,
    }


class _MockQuery:
    """Chainable mock for LanceDB query builder."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def limit(self, n: int) -> "_MockQuery":
        return self

    def where(self, condition: str) -> "_MockQuery":
        return self

    def to_list(self) -> list[dict]:
        return list(self._rows)


class _MockEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_det_vector(t) for t in texts]


SAMPLE_ROWS = [
    _make_row(
        court="BGH",
        az="IV ZR 1/24",
        date="2024-01-15",
        leitsatz="Produzentenhaftung: Der Hersteller eines fehlerhaften Produkts haftet.",
        laws_cited=["§ 823 BGB"],
        distance=0.1,
    ),
    _make_row(
        court="BAG",
        az="1 AZR 100/23",
        date="2023-06-01",
        leitsatz="Kündigungsschutz bei Betriebsübergang nach § 613a BGB.",
        laws_cited=["§ 613a BGB"],
        distance=0.2,
    ),
    _make_row(
        court="BGH",
        az="II ZR 50/22",
        date="2022-03-01",
        leitsatz="Schadensersatzpflicht bei Pflichtverletzung.",
        laws_cited=["§ 280 BGB"],
        distance=0.3,
    ),
    _make_row(
        court="BFH",
        az="VIII R 1/23",
        date="2023-11-01",
        leitsatz="Einkommensteuer bei gewerblichen Einkünften.",
        laws_cited=["§ 15 EStG"],
        distance=0.4,
    ),
]


@pytest.fixture
def retriever():
    from lex_cases.retriever import LexCaseRetriever

    r = LexCaseRetriever(db_path="/tmp/test_lancedb", embedding_provider=_MockEmbedder())

    mock_table = MagicMock()
    mock_table.search = MagicMock(return_value=_MockQuery(SAMPLE_ROWS))
    r._table = mock_table

    return r, mock_table


class TestSearch:
    def test_returns_list(self, retriever):
        r, _ = retriever
        results = r.search("Haftung")
        assert isinstance(results, list)

    def test_result_has_required_keys(self, retriever):
        r, _ = retriever
        results = r.search("Produzentenhaftung")
        assert results
        for res in results:
            for key in ("court", "az", "date", "type", "leitsatz", "laws_cited", "score", "url"):
                assert key in res, f"Missing key: {key}"

    def test_score_in_range(self, retriever):
        r, _ = retriever
        results = r.search("Haftung")
        for res in results:
            assert isinstance(res["score"], float)
            assert 0.0 <= res["score"] <= 1.0

    def test_courts_filter(self, retriever):
        r, mock_table = retriever
        mock_table.search = MagicMock(return_value=_MockQuery(SAMPLE_ROWS))
        results = r.search("Haftung", courts=["BGH"])
        assert results
        for res in results:
            assert res["court"] == "BGH"

    def test_courts_filter_excludes_non_matching(self, retriever):
        r, mock_table = retriever
        mock_table.search = MagicMock(return_value=_MockQuery(SAMPLE_ROWS))
        results = r.search("Haftung", courts=["BFH"])
        assert all(res["court"] == "BFH" for res in results)

    def test_date_from_filter(self, retriever):
        r, mock_table = retriever
        mock_table.search = MagicMock(return_value=_MockQuery(SAMPLE_ROWS))
        results = r.search("Haftung", date_from="2024-01-01")
        for res in results:
            assert res["date"] >= "2024-01-01"

    def test_date_to_filter(self, retriever):
        r, mock_table = retriever
        mock_table.search = MagicMock(return_value=_MockQuery(SAMPLE_ROWS))
        results = r.search("Haftung", date_to="2022-12-31")
        for res in results:
            assert res["date"] <= "2022-12-31"

    def test_date_range_filter(self, retriever):
        r, mock_table = retriever
        mock_table.search = MagicMock(return_value=_MockQuery(SAMPLE_ROWS))
        results = r.search("Haftung", date_from="2023-01-01", date_to="2023-12-31")
        for res in results:
            assert "2023-01-01" <= res["date"] <= "2023-12-31"

    def test_laws_cited_filter(self, retriever):
        r, mock_table = retriever
        mock_table.search = MagicMock(return_value=_MockQuery(SAMPLE_ROWS))
        results = r.search("Haftung", laws_cited=["§ 823 BGB"])
        assert results
        for res in results:
            assert "§ 823 BGB" in res["laws_cited"]

    def test_top_k_respected(self, retriever):
        r, mock_table = retriever
        mock_table.search = MagicMock(return_value=_MockQuery(SAMPLE_ROWS))
        results = r.search("Haftung", top_k=2)
        assert len(results) <= 2

    def test_dedup_by_az(self, retriever):
        r, mock_table = retriever
        # Duplicate rows with same az
        dup_rows = [_make_row(az="IV ZR 1/24", distance=0.1),
                    _make_row(az="IV ZR 1/24", distance=0.2)]
        mock_table.search = MagicMock(return_value=_MockQuery(dup_rows))
        results = r.search("test")
        aznrs = [res["az"] for res in results]
        assert len(aznrs) == len(set(aznrs))

    def test_laws_cited_is_list(self, retriever):
        r, _ = retriever
        results = r.search("Haftung")
        for res in results:
            assert isinstance(res["laws_cited"], list)


class TestGetCasesFulltext:
    def test_calls_http_get(self, retriever):
        r, _ = retriever
        mock_resp = MagicMock()
        mock_resp.content = b"<html><body><h3>Tatbestand</h3><p>Der Klager ...</p></body></html>"
        mock_resp.headers = {"Content-Type": "text/html"}

        with patch("lex_cases.retriever._http_get", return_value=mock_resp):
            text = r.get_case_fulltext("https://example.com/case")

        assert isinstance(text, str)

    def test_returns_string(self, retriever):
        r, _ = retriever
        mock_resp = MagicMock()
        mock_resp.content = b"<html><body><p>Entscheidung</p></body></html>"
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}

        with patch("lex_cases.retriever._http_get", return_value=mock_resp):
            result = r.get_case_fulltext("https://example.com/case")

        assert isinstance(result, str)

    def test_xml_content_type_uses_xml_parser(self, retriever):
        r, _ = retriever
        xml_content = b"""<?xml version="1.0"?>
        <dokument><tatbestand>Der Klager fordert Schadensersatz.</tatbestand></dokument>"""
        mock_resp = MagicMock()
        mock_resp.content = xml_content
        mock_resp.headers = {"Content-Type": "text/xml"}

        with patch("lex_cases.retriever._http_get", return_value=mock_resp):
            result = r.get_case_fulltext("https://example.com/case.xml")

        assert "Schadensersatz" in result


class TestGetCasesCitingLaw:
    def test_returns_list(self, retriever):
        r, mock_table = retriever
        mock_table.search = MagicMock(return_value=_MockQuery(SAMPLE_ROWS))
        results = r.get_cases_citing_law("BGB", "§ 823")
        assert isinstance(results, list)

    def test_filters_by_law_and_paragraph(self, retriever):
        r, mock_table = retriever
        mock_table.search = MagicMock(return_value=_MockQuery(SAMPLE_ROWS))
        results = r.get_cases_citing_law("BGB", "§ 823")
        assert results
        for res in results:
            assert "§ 823 BGB" in res["laws_cited"]

    def test_no_match_returns_empty(self, retriever):
        r, mock_table = retriever
        mock_table.search = MagicMock(return_value=_MockQuery(SAMPLE_ROWS))
        results = r.get_cases_citing_law("ZPO", "§ 91")
        assert results == []

    def test_result_has_required_keys(self, retriever):
        r, mock_table = retriever
        mock_table.search = MagicMock(return_value=_MockQuery(SAMPLE_ROWS))
        results = r.get_cases_citing_law("BGB", "§ 280")
        for res in results:
            for key in ("court", "az", "date", "type", "leitsatz", "laws_cited", "url"):
                assert key in res

    def test_dedup_by_az(self, retriever):
        r, mock_table = retriever
        dup_rows = [
            _make_row(az="IV ZR 1/24", laws_cited=["§ 823 BGB"]),
            _make_row(az="IV ZR 1/24", laws_cited=["§ 823 BGB"]),
        ]
        mock_table.search = MagicMock(return_value=_MockQuery(dup_rows))
        results = r.get_cases_citing_law("BGB", "§ 823")
        azs = [res["az"] for res in results]
        assert len(azs) == len(set(azs))


class TestParseFulltext:
    def test_parse_html_extracts_tatbestand(self):
        from lex_cases.retriever import _parse_html_fulltext

        html = (
            "<html><body>"
            "<h3>Tatbestand</h3>"
            "<p>Der Klager hat am 1. Januar Klage erhoben.</p>"
            "<h3>Entscheidungsgründe</h3>"
            "<p>Die Klage ist begründet.</p>"
            "</body></html>"
        ).encode("utf-8")
        result = _parse_html_fulltext(html)
        assert "Tatbestand" in result
        assert "Klager" in result

    def test_parse_html_extracts_entscheidungsgruende(self):
        from lex_cases.retriever import _parse_html_fulltext

        html = (
            "<html><body>"
            "<h2>Entscheidungsgründe</h2>"
            "<p>Das Gericht hat entschieden.</p>"
            "</body></html>"
        ).encode("utf-8")
        result = _parse_html_fulltext(html)
        assert "Gericht" in result

    def test_parse_xml_fulltext(self):
        from lex_cases.retriever import _parse_xml_fulltext

        xml = (
            '<?xml version="1.0"?>'
            "<dokument>"
            "<tatbestand>Der Schuldner hat die Zahlung verweigert.</tatbestand>"
            "<entscheidungsgruende>Die Klage ist zulassig und begruendet.</entscheidungsgruende>"
            "</dokument>"
        ).encode("utf-8")
        result = _parse_xml_fulltext(xml)
        assert "Schuldner" in result
        assert "zulassig" in result

    def test_parse_xml_invalid_returns_empty(self):
        from lex_cases.retriever import _parse_xml_fulltext

        result = _parse_xml_fulltext(b"not xml <<<")
        assert result == ""
