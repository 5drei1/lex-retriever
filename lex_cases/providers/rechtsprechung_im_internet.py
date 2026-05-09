"""Provider for rechtsprechung-im-internet.de — XML-ZIP download and parser."""

from __future__ import annotations

import io
import os
import re
import xml.etree.ElementTree as ET
import zipfile

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from lex_retriever.cross_reference import extract_references

from .base import CaseProvider

_COURT_CATALOG: dict[str, tuple[str, str]] = {
    "BGH":    ("Bundesgerichtshof",        "bgh"),
    "BVERFG": ("Bundesverfassungsgericht", "bverfg"),
    "BAG":    ("Bundesarbeitsgericht",     "bag"),
    "BFH":    ("Bundesfinanzhof",          "bfh"),
    "BVERWG": ("Bundesverwaltungsgericht", "bverwg"),
    "BPATG":  ("Bundespatentgericht",      "bpatg"),
}

_BASE_URL = "https://www.rechtsprechung-im-internet.de"


def _xml_zip_url(slug: str) -> str:
    return f"{_BASE_URL}/{slug}/xml.zip"


def _strip_ns(tag: str) -> str:
    """Remove XML namespace prefix from a tag name."""
    return re.sub(r"^\{[^}]+\}", "", tag)


def _find_text(root: ET.Element, local_tag: str) -> str:
    """Find first element matching local_tag (ignoring namespace) and return its full text."""
    for elem in root.iter():
        if _strip_ns(elem.tag) == local_tag:
            return " ".join(elem.itertext()).strip()
    return ""


def _parse_xml_file(xml_bytes: bytes, filename: str) -> list[dict]:
    """Parse one XML file from the ZIP; return zero or more case chunk dicts."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    doknr = _find_text(root, "doknr") or os.path.splitext(os.path.basename(filename))[0]
    court = _find_text(root, "gericht")
    date = _find_text(root, "entscheidungsdatum")
    az = _find_text(root, "aktenzeichen")
    doc_type = _find_text(root, "dokumenttyp")
    normkette = _find_text(root, "normkette")
    url = f"{_BASE_URL}/jportal/?docid={doknr}"

    laws_cited = extract_references(normkette) if normkette else []

    base: dict = {
        "court": court,
        "date": date,
        "az": az,
        "type": doc_type,
        "laws_cited": laws_cited,
        "url": url,
    }

    chunks: list[dict] = []

    leitsatz = _find_text(root, "leitsatz")
    if leitsatz:
        chunks.append({**base, "text": leitsatz, "chunk_type": "leitsatz"})

    tenor = _find_text(root, "tenor")
    if tenor:
        chunks.append({**base, "text": tenor, "chunk_type": "tenor"})

    return chunks


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    reraise=True,
)
def fetch_court_xml_zip(court: str) -> list[dict]:
    """Download XML-ZIP for a court and return parsed case dicts."""
    code = court.upper()
    entry = _COURT_CATALOG.get(code)
    if not entry:
        raise ValueError(f"Court '{court}' not in catalog; supported: {list(_COURT_CATALOG)}")

    _, slug = entry
    url = _xml_zip_url(slug)
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    chunks: list[dict] = []
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        for name in zf.namelist():
            if name.lower().endswith(".xml"):
                with zf.open(name) as f:
                    chunks.extend(_parse_xml_file(f.read(), name))

    return chunks


class RechtsprechungImInternetProvider(CaseProvider):
    """Fetches German federal court decisions from rechtsprechung-im-internet.de."""

    name = "rechtsprechung-im-internet"
    supported_courts = list(_COURT_CATALOG)

    def fetch_court(self, court: str) -> list[dict]:
        return fetch_court_xml_zip(court)
