"""Tests for the Law-Provider architecture."""

import pytest

from lex_retriever.providers.base import LawProvider
from lex_retriever.providers.gesetze_im_internet import GesetzImInternetProvider, _parse_gii_xml
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

    def test_parse_gii_xml_list_before_backreference(self):
        """Regression: § 434 Abs. 2 — numbered list must precede the back-reference sentence."""
        xml = b"""<?xml version="1.0"?>
<dokumente>
  <norm>
    <metadaten>
      <enbez>&#167; 434</enbez>
      <titel>Sachmangel</titel>
    </metadaten>
    <textdaten>
      <text>
        <Content>
          <P>(2) Die Sache entspricht den subjektiven Anforderungen, wenn sie
            <DL>
              <DT>1.</DT><DD><LA>die vereinbarte Beschaffenheit hat,</LA></DD>
              <DT>2.</DT><DD><LA>sich f&#252;r die nach dem Vertrag vorausgesetzte Verwendung eignet und</LA></DD>
              <DT>3.</DT><DD><LA>mit dem vereinbarten Zubeh&#246;r &#252;bergeben wird.</LA></DD>
            </DL>
            Zu der Beschaffenheit nach Satz 1 Nummer 1 geh&#246;ren Art, Menge, Qualit&#228;t, Funktionalit&#228;t.
          </P>
        </Content>
      </text>
    </textdaten>
  </norm>
</dokumente>"""
        chunks = _parse_gii_xml(xml, "BGB")
        assert len(chunks) == 1
        text = chunks[0]["text"]

        pos_list = text.index("die vereinbarte Beschaffenheit hat")
        pos_ref = text.index("Zu der Beschaffenheit nach Satz 1 Nummer 1")
        assert pos_list < pos_ref, (
            f"Numbered list must precede back-reference sentence; "
            f"pos_list={pos_list}, pos_ref={pos_ref}\nFull text: {text!r}"
        )

    def test_parse_gii_xml_abs3_list_before_backreference(self):
        """Regression: § 434 Abs. 3 — numbered list must precede the back-reference sentence."""
        xml = b"""<?xml version="1.0"?>
<dokumente>
  <norm>
    <metadaten>
      <enbez>&#167; 434</enbez>
      <titel>Sachmangel</titel>
    </metadaten>
    <textdaten>
      <text>
        <Content>
          <P>(3) Soweit nicht wirksam etwas anderes vereinbart wurde, entspricht die Sache den objektiven Anforderungen, wenn sie
            <DL Type="arabic">
              <DT>1.</DT><DD Font="normal"><LA>sich f&#252;r die gew&#246;hnliche Verwendung eignet,</LA></DD>
              <DT>2.</DT><DD Font="normal"><LA>eine &#252;bliche Beschaffenheit aufweist und</LA></DD>
              <DT>3.</DT><DD Font="normal"><LA>mit dem Zubeh&#246;r &#252;bergeben wird.</LA></DD>
            </DL>
            Zu der &#252;blichen Beschaffenheit nach Satz 1 Nummer 2 geh&#246;ren Menge, Qualit&#228;t und sonstige Merkmale der Sache.
          </P>
        </Content>
      </text>
    </textdaten>
  </norm>
</dokumente>"""
        chunks = _parse_gii_xml(xml, "BGB")
        assert len(chunks) == 1
        text = chunks[0]["text"]

        pos_list = text.index("sich für die gewöhnliche Verwendung eignet")
        pos_ref = text.index("Zu der üblichen Beschaffenheit nach Satz 1 Nummer 2")
        assert pos_list < pos_ref, (
            f"Numbered list must precede back-reference sentence in Abs. 3; "
            f"pos_list={pos_list}, pos_ref={pos_ref}\nFull text: {text!r}"
        )


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
