"""Tests for NeuRISProvider (offline — all API calls mocked via MockTransport)."""

from __future__ import annotations

from typing import Any

import pytest

from neuris.transport import NeuRISTransport

from lex_retriever.providers.neuris_provider import NeuRISProvider


# ── Mock transport ────────────────────────────────────────────────────────────

class MockTransport(NeuRISTransport):
    """Synchronous mock transport for offline testing."""

    base_url = "https://testphase.rechtsinformationen.bund.de/v1"

    def __init__(self) -> None:
        self._responses: dict[str, Any] = {}
        self._calls: list[tuple[str, dict[str, Any] | None]] = []

    def register(self, path: str, response: Any) -> None:
        self._responses[path] = response

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._calls.append((path, params))
        if path in self._responses:
            return self._responses[path]
        raise KeyError(f"MockTransport: no response registered for {path!r}")

    def get_raw(self, path: str, accept: str, params: dict[str, Any] | None = None) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _legislation_list(abbreviation: str, name: str, eli_work: str, parts: list[dict]) -> dict:
    return {
        "totalItems": 1,
        "member": [
            {
                "item": {
                    "@type": "Legislation",
                    "legislationIdentifier": f"{eli_work}/2024-01-01/1/deu/regelungstext-1",
                    "name": name,
                    "abbreviation": abbreviation,
                    "officialLongTitle": name,
                    "publicationDate": "2000-01-01",
                    "versionDate": "2024-01-01",
                    "eliWork": eli_work,
                    "hasPart": parts,
                },
                "textMatches": [],
            }
        ],
        "view": {"first": None, "last": None, "next": None, "previous": None},
    }


def _part_response(name: str, text: str) -> dict:
    return {
        "legislationIdentifier": "eli/bgbl-1/2024/testgesetz/2024-01-01/1/deu/regelungstext-1/art-1",
        "name": name,
        "abbreviation": "TESTG",
        "hasPart": [],
        "text": text,
    }


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_transport() -> MockTransport:
    return MockTransport()


@pytest.fixture
def provider(mock_transport: MockTransport) -> NeuRISProvider:
    return NeuRISProvider(transport=mock_transport)


def _register_law(transport: MockTransport, abbreviation: str = "TESTG") -> None:
    parts = [
        {"eli": "eli/bgbl-1/2024/testgesetz/2024-01-01/1/deu/regelungstext-1/art-1",
         "legislationWorkIdentifier": "eli/bgbl-1/2024/testgesetz/art-1"},
        {"eli": "eli/bgbl-1/2024/testgesetz/2024-01-01/1/deu/regelungstext-1/art-2",
         "legislationWorkIdentifier": "eli/bgbl-1/2024/testgesetz/art-2"},
    ]
    law_list = _legislation_list(
        abbreviation, "Testgesetz", "eli/bgbl-1/2024/testgesetz", parts
    )
    transport.register("/legislation", law_list)

    # Full legislation by ELI (hasPart may be same)
    transport.register(
        "/legislation/eli/bgbl-1/2024/testgesetz/2024-01-01/1/deu/regelungstext-1",
        law_list["member"][0]["item"],
    )

    # Individual part responses
    transport.register(
        "/legislation/eli/bgbl-1/2024/testgesetz/2024-01-01/1/deu/regelungstext-1/art-1",
        _part_response("Art. 1", "Paragraph one text."),
    )
    transport.register(
        "/legislation/eli/bgbl-1/2024/testgesetz/2024-01-01/1/deu/regelungstext-1/art-2",
        _part_response("Art. 2", "Paragraph two text."),
    )


# ── Tests: NeuRISProvider.fetch() ────────────────────────────────────────────

class TestNeuRISProviderFetch:
    def test_fetch_returns_list(self, provider: NeuRISProvider, mock_transport: MockTransport):
        _register_law(mock_transport)
        chunks = provider.fetch("TESTG")
        assert isinstance(chunks, list)

    def test_fetch_chunk_shape(self, provider: NeuRISProvider, mock_transport: MockTransport):
        _register_law(mock_transport)
        chunks = provider.fetch("TESTG")
        for chunk in chunks:
            assert "paragraph" in chunk
            assert "text" in chunk
            assert "source" in chunk

    def test_fetch_source_is_eli(self, provider: NeuRISProvider, mock_transport: MockTransport):
        _register_law(mock_transport)
        chunks = provider.fetch("TESTG")
        for chunk in chunks:
            assert chunk["source"].startswith("eli/")

    def test_fetch_returns_correct_text(self, provider: NeuRISProvider, mock_transport: MockTransport):
        _register_law(mock_transport)
        chunks = provider.fetch("TESTG")
        assert len(chunks) == 2
        texts = {c["text"] for c in chunks}
        assert "Paragraph one text." in texts
        assert "Paragraph two text." in texts

    def test_fetch_paragraph_label(self, provider: NeuRISProvider, mock_transport: MockTransport):
        _register_law(mock_transport)
        chunks = provider.fetch("TESTG")
        labels = {c["paragraph"] for c in chunks}
        assert "Art. 1" in labels
        assert "Art. 2" in labels

    def test_fetch_case_insensitive_code(self, provider: NeuRISProvider, mock_transport: MockTransport):
        _register_law(mock_transport)
        chunks_upper = provider.fetch("TESTG")
        # re-register since transport calls were consumed
        _register_law(mock_transport)
        chunks_lower = provider.fetch("testg")
        assert len(chunks_upper) == len(chunks_lower)

    def test_fetch_raises_for_unknown_law(self, provider: NeuRISProvider, mock_transport: MockTransport):
        mock_transport.register("/legislation", {
            "totalItems": 0,
            "member": [],
            "view": {"first": None, "last": None, "next": None, "previous": None},
        })
        with pytest.raises(ValueError, match="not found in NeuRIS"):
            provider.fetch("UNKNOWNLAW")

    def test_fetch_skips_parts_with_no_text(self, provider: NeuRISProvider, mock_transport: MockTransport):
        parts = [
            {"eli": "eli/bgbl-1/2024/testgesetz/2024-01-01/1/deu/regelungstext-1/art-1",
             "legislationWorkIdentifier": "eli/bgbl-1/2024/testgesetz/art-1"},
        ]
        law_list = _legislation_list("TESTG", "Testgesetz", "eli/bgbl-1/2024/testgesetz", parts)
        mock_transport.register("/legislation", law_list)
        mock_transport.register(
            "/legislation/eli/bgbl-1/2024/testgesetz/2024-01-01/1/deu/regelungstext-1",
            law_list["member"][0]["item"],
        )
        # Register part with no text fields
        mock_transport.register(
            "/legislation/eli/bgbl-1/2024/testgesetz/2024-01-01/1/deu/regelungstext-1/art-1",
            {"name": "Art. 1", "hasPart": []},  # no text field
        )
        chunks = provider.fetch("TESTG")
        assert chunks == []


# ── Tests: NeuRISProvider.is_available() ─────────────────────────────────────

class TestNeuRISProviderIsAvailable:
    def test_available_when_abbreviation_matches(self, provider: NeuRISProvider, mock_transport: MockTransport):
        mock_transport.register("/legislation", _legislation_list(
            "BGB", "Bürgerliches Gesetzbuch", "eli/bgbl-1/1896/bgb", []
        ))
        assert provider.is_available("BGB")

    def test_not_available_when_no_match(self, provider: NeuRISProvider, mock_transport: MockTransport):
        mock_transport.register("/legislation", {
            "totalItems": 0,
            "member": [],
            "view": {"first": None, "last": None, "next": None, "previous": None},
        })
        assert not provider.is_available("UNKNOWNLAW")

    def test_is_available_case_insensitive(self, provider: NeuRISProvider, mock_transport: MockTransport):
        mock_transport.register("/legislation", _legislation_list(
            "BGB", "Bürgerliches Gesetzbuch", "eli/bgbl-1/1896/bgb", []
        ))
        assert provider.is_available("bgb")


# ── Tests: provider identity ──────────────────────────────────────────────────

class TestNeuRISProviderIdentity:
    def test_name(self, provider: NeuRISProvider):
        assert provider.name == "neuris"

    def test_supported_laws_is_empty_list(self, provider: NeuRISProvider):
        # NeuRISProvider is dynamic; supported_laws is intentionally empty
        assert provider.supported_laws == []


# ── Tests: registry integration ───────────────────────────────────────────────

class TestNeuRISInRegistry:
    def test_neuris_provider_is_in_registry(self):
        from lex_retriever.providers import REGISTRY
        names = [p.name for p in REGISTRY]
        assert "neuris" in names

    def test_neuris_provider_class_registered(self):
        from lex_retriever.providers import REGISTRY
        types = [type(p).__name__ for p in REGISTRY]
        assert "NeuRISProvider" in types
