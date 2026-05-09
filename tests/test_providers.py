"""Tests for the Law-Provider architecture."""

import pytest

from lex_retriever.providers.base import LawProvider
from lex_retriever.providers.gesetze_im_internet import GesetzImInternetProvider
from lex_retriever.providers import REGISTRY, get_providers_for_law, all_supported_laws


# ---------------------------------------------------------------------------
# ExampleProvider — dummy provider for testing the pluggable architecture
# ---------------------------------------------------------------------------

class ExampleProvider(LawProvider):
    """Example provider: returns hardcoded fake law chunks for testing."""

    name = "example"
    supported_laws = ["TESTLAW", "DEMOLAW"]

    def fetch(self, law_code: str) -> list[dict]:
        if not self.is_available(law_code):
            raise ValueError(f"Unsupported law: {law_code}")
        return [
            {
                "paragraph": "§ 1",
                "text": f"This is paragraph 1 of {law_code}.",
                "source": f"example/{law_code}",
            },
            {
                "paragraph": "§ 2",
                "text": f"This is paragraph 2 of {law_code}.",
                "source": f"example/{law_code}",
            },
        ]


# ---------------------------------------------------------------------------
# LawProvider base class
# ---------------------------------------------------------------------------

class TestLawProviderBase:
    def test_is_available_case_insensitive(self):
        p = ExampleProvider()
        assert p.is_available("TESTLAW")
        assert p.is_available("testlaw")
        assert p.is_available("TestLaw")

    def test_is_available_false(self):
        p = ExampleProvider()
        assert not p.is_available("BGB")

    def test_fetch_returns_chunks(self):
        p = ExampleProvider()
        chunks = p.fetch("TESTLAW")
        assert len(chunks) == 2
        for chunk in chunks:
            assert "paragraph" in chunk
            assert "text" in chunk
            assert "source" in chunk

    def test_fetch_unsupported_raises(self):
        p = ExampleProvider()
        with pytest.raises(ValueError):
            p.fetch("BGB")


# ---------------------------------------------------------------------------
# GesetzImInternetProvider unit tests (no network)
# ---------------------------------------------------------------------------

class TestGesetzImInternetProvider:
    def test_supported_laws(self):
        p = GesetzImInternetProvider()
        assert "BGB" in p.supported_laws
        assert "HGB" in p.supported_laws
        assert "GmbHG" in p.supported_laws
        assert "GewO" in p.supported_laws

    def test_is_available(self):
        p = GesetzImInternetProvider()
        assert p.is_available("BGB")
        assert p.is_available("bgb")
        assert not p.is_available("STGB")

    def test_name(self):
        p = GesetzImInternetProvider()
        assert p.name == "gesetze-im-internet"


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

class TestProviderRegistry:
    def test_registry_not_empty(self):
        assert len(REGISTRY) > 0

    def test_all_supported_laws_includes_bgb(self):
        laws = all_supported_laws()
        assert "BGB" in laws

    def test_get_providers_for_bgb(self):
        providers = get_providers_for_law("BGB")
        assert len(providers) > 0

    def test_get_providers_for_unknown_law(self):
        providers = get_providers_for_law("UNKNOWNLAW")
        assert providers == []

    def test_pluggable_registration(self):
        """Demonstrate that registering a new provider works without core changes."""
        example = ExampleProvider()
        original_count = len(REGISTRY)
        REGISTRY.append(example)
        try:
            providers = get_providers_for_law("TESTLAW")
            assert any(p.name == "example" for p in providers)
        finally:
            REGISTRY.pop()
            assert len(REGISTRY) == original_count
