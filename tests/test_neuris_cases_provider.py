"""Tests for NeurisCasesProvider using a mock NeuRIS transport."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest

from neuris.transport import NeuRISTransport
from lex_cases.providers.base import CaseProvider
from lex_cases.providers.neuris_cases_provider import (
    NeurisCasesProvider,
    _COURT_CATALOG,
)


# ── Mock transport ────────────────────────────────────────────────────────────

class _MockTransport(NeuRISTransport):
    base_url = "https://testphase.rechtsinformationen.bund.de/v1"

    def __init__(self, responses: dict[str, Any]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict | None]] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((path, params))
        for key, value in self._responses.items():
            if path.startswith(key):
                return value
        raise KeyError(f"No mock response for {path!r}")

    def close(self) -> None:
        pass


def _single_page_response(court_type: str = "BGH") -> dict[str, Any]:
    return {
        "@type": "hydra:Collection",
        "totalItems": 2,
        "member": [
            {
                "item": {
                    "@type": "Decision",
                    "documentNumber": "BGHE-001",
                    "ecli": "ECLI:DE:BGH:2024:001",
                    "guidingPrinciple": "Leitsatz 1",
                    "tenor": "Tenor 1",
                    "decisionDate": "2024-03-01",
                    "fileNumbers": ["II ZR 1/24"],
                    "courtType": court_type,
                    "courtLocation": "Karlsruhe",
                    "courtLabel": "Bundesgerichtshof",
                    "legalEffect": "rechtskräftig",
                    "documentType": "Urteil",
                    "yearOfDecision": "2024",
                    "headline": None,
                    "documentationOffice": "BGH",
                },
                "textMatches": [],
            },
            {
                "item": {
                    "@type": "Decision",
                    "documentNumber": "BGHE-002",
                    "ecli": None,
                    "guidingPrinciple": None,
                    "tenor": None,
                    "decisionDate": None,
                    "fileNumbers": [],
                    "courtType": court_type,
                    "courtLocation": "Karlsruhe",
                    "courtLabel": "Bundesgerichtshof",
                    "legalEffect": None,
                    "documentType": "Beschluss",
                    "yearOfDecision": "2024",
                    "headline": None,
                    "documentationOffice": "BGH",
                },
                "textMatches": [],
            },
        ],
        "view": {
            "@type": "PartialCollectionView",
            "first": None,
            "last": None,
            "next": None,
            "previous": None,
        },
    }


# ── Provider contract tests ───────────────────────────────────────────────────

class TestNeurisCasesProviderContract:
    def test_is_case_provider(self):
        transport = _MockTransport({"/case-law": _single_page_response()})
        assert isinstance(NeurisCasesProvider(transport=transport), CaseProvider)

    def test_name(self):
        p = NeurisCasesProvider()
        assert p.name == "neuris"

    def test_supported_courts_has_all_six(self):
        p = NeurisCasesProvider()
        for court in ("BGH", "BVERFG", "BAG", "BFH", "BVERWG", "BPATG"):
            assert court in p.supported_courts

    def test_unsupported_court_raises_value_error(self):
        p = NeurisCasesProvider()
        with pytest.raises(ValueError, match="not in catalog"):
            p.fetch_court("UNKNOWN")

    def test_court_code_case_insensitive(self):
        transport = _MockTransport({"/case-law": _single_page_response()})
        p = NeurisCasesProvider(transport=transport)
        result = p.fetch_court("bgh")
        assert isinstance(result, list)


class TestNeurisCasesProviderFetchCourt:
    def _make_provider(self, response: dict | None = None) -> tuple[NeurisCasesProvider, _MockTransport]:
        resp = response if response is not None else _single_page_response()
        transport = _MockTransport({"/case-law": resp})
        return NeurisCasesProvider(transport=transport), transport

    def test_returns_list(self):
        p, _ = self._make_provider()
        result = p.fetch_court("BGH")
        assert isinstance(result, list)

    def test_returns_correct_count(self):
        p, _ = self._make_provider()
        result = p.fetch_court("BGH")
        assert len(result) == 2

    def test_each_dict_has_document_number(self):
        p, _ = self._make_provider()
        for item in p.fetch_court("BGH"):
            assert "documentNumber" in item
            assert item["documentNumber"]

    def test_each_dict_has_required_metadata(self):
        p, _ = self._make_provider()
        for item in p.fetch_court("BGH"):
            assert "court" in item
            assert "date" in item
            assert "az" in item
            assert "type" in item

    def test_no_fulltext_in_dict(self):
        p, _ = self._make_provider()
        for item in p.fetch_court("BGH"):
            assert "text" not in item
            assert "chunk_type" not in item
            assert "guiding_principle" not in item
            assert "tenor" not in item

    def test_document_number_values(self):
        p, _ = self._make_provider()
        result = p.fetch_court("BGH")
        doc_numbers = {r["documentNumber"] for r in result}
        assert doc_numbers == {"BGHE-001", "BGHE-002"}

    def test_court_label_populated(self):
        p, _ = self._make_provider()
        result = p.fetch_court("BGH")
        assert result[0]["court"] == "Bundesgerichtshof"

    def test_date_populated(self):
        p, _ = self._make_provider()
        result = p.fetch_court("BGH")
        assert result[0]["date"] == "2024-03-01"

    def test_date_empty_when_none(self):
        p, _ = self._make_provider()
        result = p.fetch_court("BGH")
        assert result[1]["date"] == ""

    def test_az_from_first_file_number(self):
        p, _ = self._make_provider()
        result = p.fetch_court("BGH")
        assert result[0]["az"] == "II ZR 1/24"

    def test_az_empty_when_no_file_numbers(self):
        p, _ = self._make_provider()
        result = p.fetch_court("BGH")
        assert result[1]["az"] == ""

    def test_type_populated(self):
        p, _ = self._make_provider()
        result = p.fetch_court("BGH")
        assert result[0]["type"] == "Urteil"

    def test_ecli_populated(self):
        p, _ = self._make_provider()
        result = p.fetch_court("BGH")
        assert result[0]["ecli"] == "ECLI:DE:BGH:2024:001"

    def test_ecli_empty_when_none(self):
        p, _ = self._make_provider()
        result = p.fetch_court("BGH")
        assert result[1]["ecli"] == ""

    def test_legal_effect_populated(self):
        p, _ = self._make_provider()
        result = p.fetch_court("BGH")
        assert result[0]["legal_effect"] == "rechtskräftig"

    def test_legal_effect_empty_when_none(self):
        p, _ = self._make_provider()
        result = p.fetch_court("BGH")
        assert result[1]["legal_effect"] == ""

    def test_api_called_with_correct_court_code(self):
        _, transport = self._make_provider()
        NeurisCasesProvider(transport=transport).fetch_court("BGH")
        _, params = transport.calls[0]
        assert params is not None
        assert params.get("court") == "BGH"

    def test_bverwg_maps_to_bverwg_code(self):
        transport = _MockTransport({"/case-law": _single_page_response("BVerwG")})
        NeurisCasesProvider(transport=transport).fetch_court("BVERWG")
        _, params = transport.calls[0]
        assert params["court"] == "BVerwG"

    def test_bverfg_maps_to_bverfg_code(self):
        transport = _MockTransport({"/case-law": _single_page_response("BVerfG")})
        NeurisCasesProvider(transport=transport).fetch_court("BVERFG")
        _, params = transport.calls[0]
        assert params["court"] == "BVerfG"

    def test_bpatg_maps_to_bpatg_code(self):
        transport = _MockTransport({"/case-law": _single_page_response("BPatG")})
        NeurisCasesProvider(transport=transport).fetch_court("BPATG")
        _, params = transport.calls[0]
        assert params["court"] == "BPatG"

    def test_empty_result_when_no_decisions(self):
        empty = {
            "@type": "hydra:Collection",
            "totalItems": 0,
            "member": [],
            "view": {"first": None, "last": None, "next": None, "previous": None},
        }
        transport = _MockTransport({"/case-law": empty})
        result = NeurisCasesProvider(transport=transport).fetch_court("BFH")
        assert result == []

    def test_all_catalog_courts_accepted(self):
        for court_code, neuris_code in _COURT_CATALOG.items():
            transport = _MockTransport({"/case-law": _single_page_response(neuris_code)})
            result = NeurisCasesProvider(transport=transport).fetch_court(court_code)
            assert isinstance(result, list)
