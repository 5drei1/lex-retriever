import io
import re
import zipfile
from xml.etree import ElementTree as ET

import requests

from .base import LawProvider

# Map of known law codes to their gesetze-im-internet.de XML-ZIP paths
_LAW_URLS = {
    "BGB": "https://www.gesetze-im-internet.de/bgb/xml.zip",
    "HGB": "https://www.gesetze-im-internet.de/hgb/xml.zip",
    "GMBHG": "https://www.gesetze-im-internet.de/gmbhg/xml.zip",
    "GEWO": "https://www.gesetze-im-internet.de/gewo/xml.zip",
    "BDSG_2018": "https://www.gesetze-im-internet.de/bdsg_2018/xml.zip",
}

# Namespace used in GII XML files
_NS = {"ns": "http://www.juris.de/jportal/namespace/types/de/documentTypes/norm/1.0.0"}


def _parse_gii_xml(xml_bytes: bytes, law_code: str) -> list[dict]:
    """Parse a single GII XML file into paragraph chunks."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    chunks = []
    # GII XML: each <norm> contains <metadaten> (metadata) and <textdaten> (content)
    for norm in root.findall(".//norm", _NS):
        enbez = norm.findtext("metadaten/enbez", default="", namespaces=_NS) or ""
        titel = norm.findtext("metadaten/titel", default="", namespaces=_NS) or ""

        # Extract paragraph identifier
        paragraph = enbez.strip()
        if titel:
            paragraph = f"{paragraph} ({titel.strip()})" if paragraph else titel.strip()

        # Collect all text content from <Content> nodes
        text_parts = []
        for content in norm.findall(".//Content", _NS):
            if content.text:
                text_parts.append(content.text.strip())
        for elem in norm.findall(".//textdaten//"):
            if elem.text and elem.text.strip():
                text_parts.append(elem.text.strip())
            if elem.tail and elem.tail.strip():
                text_parts.append(elem.tail.strip())

        text = " ".join(text_parts).strip()
        # Fallback: get all text in the norm element
        if not text:
            text = " ".join(norm.itertext()).strip()
            text = re.sub(r"\s+", " ", text)

        if text:
            chunks.append({
                "paragraph": paragraph or "§ (unbekannt)",
                "text": text,
                "source": f"gesetze-im-internet.de/{law_code}",
            })

    return chunks


class GesetzImInternetProvider(LawProvider):
    """Fetches German laws from gesetze-im-internet.de as XML-ZIP archives."""

    name = "gesetze-im-internet"
    supported_laws = list(_LAW_URLS.keys())

    def fetch(self, law_code: str) -> list[dict]:
        url = _LAW_URLS.get(law_code.upper())
        if not url:
            raise ValueError(f"Law '{law_code}' not supported by {self.name}")

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        chunks = []
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            for name in zf.namelist():
                if name.endswith(".xml"):
                    with zf.open(name) as f:
                        chunks.extend(_parse_gii_xml(f.read(), law_code.upper()))

        return chunks
