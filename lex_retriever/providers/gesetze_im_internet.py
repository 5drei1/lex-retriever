import io
import re
import zipfile
from xml.etree import ElementTree as ET

import requests

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


def _paragraph_source_slug(paragraph: str) -> str:
    """Build a stable, paragraph-specific URI slug for source attribution."""
    cleaned = re.sub(r"\s+", "-", paragraph.strip().lower())
    return re.sub(r"[^a-z0-9\-§äöüß().]", "", cleaned)


def _parse_gii_xml(xml_bytes: bytes, law_code: str) -> list[dict]:
    """Parse a single GII XML file into paragraph chunks."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    chunks = []
    norms = root.findall(".//ns:norm", _NS) or root.findall(".//norm")
    for norm in norms:
        enbez = norm.findtext("metadaten/enbez", default="", namespaces=_NS) or ""
        titel = norm.findtext("metadaten/titel", default="", namespaces=_NS) or ""

        paragraph = enbez.strip()
        if titel:
            paragraph = f"{paragraph} ({titel.strip()})" if paragraph else titel.strip()

        textdaten = norm.find(".//textdaten")
        if textdaten is not None:
            text_parts = [t.strip() for t in textdaten.itertext() if t and t.strip()]
            text = re.sub(r"\s+", " ", " ".join(text_parts)).strip()
        else:
            text = re.sub(r"\s+", " ", " ".join(norm.itertext())).strip()

        # Skip malformed/empty norm entries instead of indexing unknown fallbacks.
        # Require enbez to avoid indexing pure title headings.
        if text and enbez.strip():
            chunks.append({
                "paragraph": paragraph,
                "text": text,
                "source": (
                    f"gesetze-im-internet.de/{law_code}/{_paragraph_source_slug(paragraph)}"
                ),
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
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        chunks = []
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            for name in zf.namelist():
                if name.endswith(".xml"):
                    with zf.open(name) as f:
                        chunks.extend(_parse_gii_xml(f.read(), code))

        return chunks

    def fetch_text(self, ref_id: str, paragraph: str) -> str:
        # ref_id formats supported:
        # - "gesetze-im-internet.de/{LAW_CODE}" (legacy)
        # - "gesetze-im-internet.de/{LAW_CODE}/{paragraph-slug}" (paragraph-specific)
        try:
            parts = ref_id.split("/")
            if "gesetze-im-internet.de" in parts:
                base_idx = parts.index("gesetze-im-internet.de")
                law_code = parts[base_idx + 1]
            else:
                law_code = parts[-1]
            for chunk in self.fetch(law_code):
                if chunk["paragraph"] == paragraph:
                    return chunk["text"]
        except Exception:
            pass
        return ""
