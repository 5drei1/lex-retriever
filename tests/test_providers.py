"""Tests for the Law-Provider architecture."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from lex_retriever.providers.base import LawProvider
from lex_retriever.providers.gesetze_im_internet import (
    GesetzImInternetProvider,
    _fetch_with_retry,
)
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
        assert "GMBHG" in p.supported_laws
        assert "GEWO" in p.supported_laws

    def test_is_available(self):
        p = GesetzImInternetProvider()
        assert p.is_available("BGB")
        assert p.is_available("bgb")
        # STGB is in _LAW_CATALOG so it is available; check a truly unknown code
        assert p.is_available("STGB")
        assert not p.is_available("UNKNOWN_LAW_XYZ")

    def test_name(self):
        p = GesetzImInternetProvider()
        assert p.name == "gesetze-im-internet"

    def test_fetch_with_retry_retries_on_network_error(self):
        """_fetch_with_retry retries up to 3 times before giving up (reraise=True)."""
        from tenacity import wait_none

        mock_get = MagicMock(side_effect=requests.ConnectionError("timeout"))
        fast_fetch = _fetch_with_retry.retry_with(wait=wait_none())
        with patch(
            "lex_retriever.providers.gesetze_im_internet.requests.get",
            mock_get,
        ):
            with pytest.raises(requests.ConnectionError):
                fast_fetch("https://example.com/test.zip")
        assert mock_get.call_count == 3

    def test_fetch_with_retry_succeeds_after_transient_error(self):
        """_fetch_with_retry returns content when a later attempt succeeds."""
        from tenacity import wait_none

        ok_response = MagicMock()
        ok_response.content = b"data"
        ok_response.raise_for_status = MagicMock()

        fast_fetch = _fetch_with_retry.retry_with(wait=wait_none())
        with patch(
            "lex_retriever.providers.gesetze_im_internet.requests.get",
            side_effect=[requests.ConnectionError("timeout"), ok_response],
        ) as mock_get:
            result = fast_fetch("https://example.com/test.zip")
        assert result == b"data"
        assert mock_get.call_count == 2

    def test_fetch_raises_runtime_error_after_all_retries_exhausted(self):
        """fetch() raises RuntimeError with URL after 3 failed attempts."""
        with patch(
            "lex_retriever.providers.gesetze_im_internet._fetch_with_retry",
            side_effect=requests.ConnectionError("network down"),
        ):
            p = GesetzImInternetProvider()
            with pytest.raises(RuntimeError, match="Failed to fetch.*bgb.*3 attempts"):
                p.fetch("BGB")


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
