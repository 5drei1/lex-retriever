from lex_retriever.providers.gesetze_im_internet import _is_indexable_enbez, _parse_gii_xml


def test_parse_gii_xml_skips_norm_without_paragraph_identifier():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<dokument>
  <norm>
    <metadaten>
      <enbez>  </enbez>
      <titel> </titel>
    </metadaten>
    <textdaten>
      <text>
        <Content>Inhalt ohne gueltige Normbezeichnung.</Content>
      </text>
    </textdaten>
  </norm>
  <norm>
    <metadaten>
      <enbez>&#167; 1</enbez>
      <titel>Geltungsbereich</titel>
    </metadaten>
    <textdaten>
      <text>
        <Content>Dies ist gueltiger Normtext.</Content>
      </text>
    </textdaten>
  </norm>
</dokument>
""".encode("utf-8")
    chunks = _parse_gii_xml(xml, "BGB")

    assert len(chunks) == 1
    assert chunks[0]["paragraph"] == "§ 1 (Geltungsbereich)"
    assert "gueltiger Normtext" in chunks[0]["text"]


def test_parse_gii_xml_skips_non_normative_enbez_values():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<dokument>
  <norm>
    <metadaten><enbez>Inhaltsuebersicht</enbez></metadaten>
    <textdaten><text><Content>Nur Ueberschrift.</Content></text></textdaten>
  </norm>
  <norm>
    <metadaten><enbez>Anlage 1</enbez></metadaten>
    <textdaten><text><Content>Anlage ohne Paragraph.</Content></text></textdaten>
  </norm>
  <norm>
    <metadaten><enbez>Art. 3</enbez></metadaten>
    <textdaten><text><Content>Alle Menschen sind vor dem Gesetz gleich.</Content></text></textdaten>
  </norm>
</dokument>
""".encode("utf-8")
    chunks = _parse_gii_xml(xml, "GG")
    assert [c["paragraph"] for c in chunks] == ["Art. 3"]


def test_is_indexable_enbez_accepts_only_paragraph_or_article_patterns():
    assert _is_indexable_enbez("§ 1")
    assert _is_indexable_enbez("§§ 80")
    assert _is_indexable_enbez("Art. 3")
    assert _is_indexable_enbez("art 20")
    assert not _is_indexable_enbez("")
    assert not _is_indexable_enbez("Inhaltsuebersicht")
    assert not _is_indexable_enbez("Anlage 1")
