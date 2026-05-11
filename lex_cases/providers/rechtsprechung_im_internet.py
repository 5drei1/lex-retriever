"""Provider for rechtsprechung-im-internet.de.

DEPRECATED: Use NeurisCasesProvider (neuris_cases_provider.py) instead.

Bulk-ZIP approach (/{court}/xml.zip) is blocked by the server and returns HTML.
Instead we: (1) parse the RSS feed to enumerate recent doc-IDs, then (2) fetch
each individual ZIP at /jportal/docs/bsjrs/{doc_id}.zip.
This covers the ~200 most recent decisions per court per feed poll.
"""

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
_RSS_URL = f"{_BASE_URL}/jportal/docs/feed/bsjrs-{{slug}}.xml"
_CASE_ZIP_URL = f"{_BASE_URL}/jportal/docs/bsjrs/{{doc_id}}.zip"


def _strip_ns(tag: str) -> str:
    return re.sub(r"^\{[^}]+\}", "", tag)


def _find_text(root: ET.Element, local_tag: str) -> str:
    for elem in root.iter():
        if _strip_ns(elem.tag) == local_tag:
            return " ".join(elem.itertext()).strip()
    return ""


def _parse_xml_file(xml_bytes: bytes, filename: str) -> list[dict]:
    """Parse one case XML file; return zero or more chunk dicts."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    doknr = _find_text(root, "doknr") or os.path.splitext(os.path.basename(filename))[0]
    court = _find_text(root, "gertyp") or _find_text(root, "gericht")
    date = _find_text(root, "entsch-datum") or _find_text(root, "entscheidungsdatum")
    az = _find_text(root, "aktenzeichen")
    doc_type = _find_text(root, "doktyp") or _find_text(root, "dokumenttyp")
    normkette = _find_text(root, "norm") or _find_text(root, "normkette")
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
def _fetch_rss_doc_ids(slug: str) -> list[str]:
    """Return list of doc-IDs from the RSS feed for a court slug."""
    url = _RSS_URL.format(slug=slug)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    doc_ids: list[str] = []
    for item in root.findall(".//item"):
        guid = item.find("guid")
        if guid is not None and guid.text:
            doc_ids.append(guid.text.strip())
    return doc_ids


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    reraise=True,
)
def _fetch_case_zip(doc_id: str) -> list[dict]:
    """Download individual case ZIP and return parsed chunk dicts."""
    url = _CASE_ZIP_URL.format(doc_id=doc_id)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    chunks: list[dict] = []
    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".xml"):
                    with zf.open(name) as f:
                        chunks.extend(_parse_xml_file(f.read(), name))
    except zipfile.BadZipFile:
        pass
    return chunks


def fetch_court_via_rss(court: str) -> list[dict]:
    """Fetch recent decisions for a court via RSS feed + per-case ZIPs."""
    code = court.upper()
    entry = _COURT_CATALOG.get(code)
    if not entry:
        raise ValueError(f"Court '{court}' not in catalog; supported: {list(_COURT_CATALOG)}")

    _, slug = entry
    doc_ids = _fetch_rss_doc_ids(slug)

    chunks: list[dict] = []
    for doc_id in doc_ids:
        try:
            chunks.extend(_fetch_case_zip(doc_id))
        except Exception:
            continue

    return chunks


class RechtsprechungImInternetProvider(CaseProvider):
    """Fetches recent German federal court decisions via RSS feed + per-case ZIPs.

    The court-level xml.zip endpoint is blocked by the server (returns HTML).
    This provider uses the RSS feed to enumerate recent doc-IDs and downloads
    each decision individually from /jportal/docs/bsjrs/{doc_id}.zip.

    .. deprecated::
        Use NeurisCasesProvider instead.
    """

    name = "rechtsprechung-im-internet"
    supported_courts = list(_COURT_CATALOG)

    def __init__(self) -> None:
        import warnings
        warnings.warn(
            "RechtsprechungImInternetProvider is deprecated; use NeurisCasesProvider instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    def fetch_court(self, court: str) -> list[dict]:
        return fetch_court_via_rss(court)
