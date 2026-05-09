import io
import re
import zipfile
from xml.etree import ElementTree as ET

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .base import LawProvider

# Comprehensive catalog: CODE -> (full_name, slug)
# Slug determines the XML-ZIP URL: https://www.gesetze-im-internet.de/{slug}/xml.zip
_LAW_CATALOG: dict[str, tuple[str, str]] = {
    # Civil & Commercial Law
    "BGB":       ("Bürgerliches Gesetzbuch",                           "bgb"),
    "HGB":       ("Handelsgesetzbuch",                                  "hgb"),
    "GMBHG":     ("GmbH-Gesetz",                                        "gmbhg"),
    "AKTG":      ("Aktiengesetz",                                       "aktg"),
    "GEWO":      ("Gewerbeordnung",                                     "gewo"),
    "INSO":      ("Insolvenzordnung",                                   "inso"),
    "URHG":      ("Urheberrechtsgesetz",                                "urhg"),
    "UMWG":      ("Umwandlungsgesetz",                                  "umwg"),
    "WPHG":      ("Wertpapierhandelsgesetz",                            "wphg"),
    "PATG":      ("Patentgesetz",                                       "patg"),
    "MARKENG":   ("Markengesetz",                                       "markeng"),
    "WBVG":      ("Wohn- und Betreuungsvertragsgesetz",                 "wbvg"),
    # Data Protection & Media
    "BDSG_2018": ("Bundesdatenschutzgesetz",                            "bdsg_2018"),
    "TMG":       ("Telemediengesetz",                                   "tmg"),
    # Criminal Law
    "STGB":      ("Strafgesetzbuch",                                    "stgb"),
    "STPO":      ("Strafprozessordnung",                                "stpo"),
    "JGG":       ("Jugendgerichtsgesetz",                               "jgg"),
    # Procedural Law
    "ZPO":       ("Zivilprozessordnung",                                "zpo"),
    "GVG":       ("Gerichtsverfassungsgesetz",                          "gvg"),
    "VWGO":      ("Verwaltungsgerichtsordnung",                         "vwgo"),
    "FGO":       ("Finanzgerichtsordnung",                              "fgo"),
    "ARBGG":     ("Arbeitsgerichtsgesetz",                              "arbgg"),
    # Constitutional & Administrative Law
    "GG":        ("Grundgesetz",                                        "gg"),
    "VWVFG":     ("Verwaltungsverfahrensgesetz",                        "vwvfg"),
    # Labor Law
    "AGG":       ("Allgemeines Gleichbehandlungsgesetz",                "agg"),
    "KSCHG":     ("Kündigungsschutzgesetz",                             "kschg"),
    "TZBFG":     ("Teilzeit- und Befristungsgesetz",                    "tzbfg"),
    "BETRVG":    ("Betriebsverfassungsgesetz",                          "betrvg"),
    "ARBZG":     ("Arbeitszeitgesetz",                                  "arbzg"),
    "BURLG":     ("Bundesurlaubsgesetz",                                "burlg"),
    "MUSCHG":    ("Mutterschutzgesetz",                                 "muschg"),
    "JARBSCHG":  ("Jugendarbeitsschutzgesetz",                          "jarbschg"),
    # Social Law
    "SGB_1":     ("Sozialgesetzbuch Erstes Buch",                       "sgb_1"),
    "SGB_2":     ("Sozialgesetzbuch Zweites Buch (Bürgergeld)",         "sgb_2"),
    "SGB_5":     ("Sozialgesetzbuch Fünftes Buch (Krankenversicherung)","sgb_5"),
    # Traffic Law
    "STVG":      ("Straßenverkehrsgesetz",                              "stvg"),
    # Tax Law
    "ESTG":      ("Einkommensteuergesetz",                              "estg"),
    "USTG":      ("Umsatzsteuergesetz",                                 "ustg"),
}

# Laws active by default (used when no lex_retriever.toml present)
_DEFAULT_ACTIVE = ["BGB", "HGB", "GMBHG", "GEWO", "BDSG_2018"]

# Namespace used in GII XML files
_NS = {"ns": "http://www.juris.de/jportal/namespace/types/de/documentTypes/norm/1.0.0"}


def _xml_zip_url(slug: str) -> str:
    return f"https://www.gesetze-im-internet.de/{slug}/xml.zip"


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _fetch_with_retry(url: str) -> bytes:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


def _parse_gii_xml(xml_bytes: bytes, law_code: str) -> list[dict]:
    """Parse a single GII XML file into paragraph chunks."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    chunks = []
    for norm in root.findall(".//norm", _NS):
        enbez = norm.findtext("metadaten/enbez", default="", namespaces=_NS) or ""
        titel = norm.findtext("metadaten/titel", default="", namespaces=_NS) or ""

        paragraph = enbez.strip()
        if titel:
            paragraph = f"{paragraph} ({titel.strip()})" if paragraph else titel.strip()

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
    supported_laws = _DEFAULT_ACTIVE

    def available_laws(self) -> list[dict]:
        return [
            {"code": code, "full_name": name, "url": _xml_zip_url(slug)}
            for code, (name, slug) in sorted(_LAW_CATALOG.items())
        ]

    def is_available(self, law_code: str) -> bool:
        return law_code.upper() in _LAW_CATALOG

    def fetch(self, law_code: str) -> list[dict]:
        code = law_code.upper()
        entry = _LAW_CATALOG.get(code)
        if not entry:
            raise ValueError(f"Law '{law_code}' not in catalog for {self.name}")

        _, slug = entry
        url = _xml_zip_url(slug)
        content = _fetch_with_retry(url)

        chunks = []
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                if name.endswith(".xml"):
                    with zf.open(name) as f:
                        chunks.extend(_parse_gii_xml(f.read(), code))

        return chunks
