from lex_retriever.providers.gesetze_im_internet import _parse_gii_xml


def test_parse_gii_xml_skips_norm_without_paragraph_identifier():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
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
      <enbez>PARA 1</enbez>
      <titel>Geltungsbereich</titel>
    </metadaten>
    <textdaten>
      <text>
        <Content>Dies ist gueltiger Normtext.</Content>
      </text>
    </textdaten>
  </norm>
</dokument>
"""
    chunks = _parse_gii_xml(xml, "BGB")

    assert len(chunks) == 1
    assert chunks[0]["paragraph"] == "PARA 1 (Geltungsbereich)"
    assert "gueltiger Normtext" in chunks[0]["text"]
