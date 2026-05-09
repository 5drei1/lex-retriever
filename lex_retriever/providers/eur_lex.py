"""EUR-Lex provider: fetches EU regulations from eur-lex.europa.eu."""

import re
from xml.etree import ElementTree as ET

import requests

from .base import LawProvider

_LAW_URLS = {
    "DSGVO": "https://eur-lex.europa.eu/legal-content/DE/TXT/XML/?uri=CELEX:32016R0679",
    # Add more EU regulations here — no core code changes needed
}

# EUR-Lex Akoma Ntoso XML namespace
_NS = {
    "akn": "http://docs.oasis-open.org/legaldocml/ns/akn/3.0",
    "fmx": "http://formex.publications.europa.eu/schema/formex-05.56-20160701.xd",
}


def _extract_text(element) -> str:
    """Recursively collect all text from an XML element."""
    return re.sub(r"\s+", " ", " ".join(element.itertext())).strip()


def _parse_eur_lex_xml(xml_bytes: bytes, law_code: str) -> list[dict]:
    """Parse EUR-Lex XML (Akoma Ntoso / Formex) into paragraph chunks."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    chunks = []
    source = f"eur-lex.europa.eu/CELEX:{_CELEX.get(law_code, law_code)}"

    # Try Akoma Ntoso structure first (articles inside body/act)
    articles = root.findall(".//{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}article")
    if articles:
        for article in articles:
            num_el = article.find("{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}num")
            num = num_el.text.strip() if num_el is not None and num_el.text else ""
            heading_el = article.find("{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}heading")
            heading = heading_el.text.strip() if heading_el is not None and heading_el.text else ""
            paragraph = f"Art. {num}" if num else "Art. (unbekannt)"
            if heading:
                paragraph = f"{paragraph} — {heading}"
            text = _extract_text(article)
            if text:
                chunks.append({"paragraph": paragraph, "text": text, "source": source})
        return chunks

    # Fallback: look for generic article-like elements (ARTICLE, article, Article)
    for tag_name in ("ARTICLE", "article", "Article", "ARTIKEL"):
        elements = root.iter(tag_name)
        for el in elements:
            num = el.get("NO") or el.get("num") or el.get("id") or ""
            paragraph = f"Art. {num}" if num else "Art."
            text = _extract_text(el)
            if text:
                chunks.append({"paragraph": paragraph, "text": text, "source": source})
        if chunks:
            return chunks

    # Last resort: split into large text blocks by top-level children
    for i, child in enumerate(root, start=1):
        text = _extract_text(child)
        if text and len(text) > 50:
            chunks.append({"paragraph": f"Abschnitt {i}", "text": text, "source": source})

    return chunks


_CELEX = {
    "DSGVO": "32016R0679",
}


class EurLexProvider(LawProvider):
    """Fetches EU regulations from eur-lex.europa.eu in German (XML)."""

    name = "eur-lex"
    supported_laws = list(_LAW_URLS.keys())

    def fetch(self, law_code: str) -> list[dict]:
        url = _LAW_URLS.get(law_code.upper())
        if not url:
            raise ValueError(f"Law '{law_code}' not supported by {self.name}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return _parse_eur_lex_xml(response.content, law_code.upper())
