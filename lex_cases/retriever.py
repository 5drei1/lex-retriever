"""Retriever: semantic search over LanceDB-indexed Leitsätze and on-demand fulltext fetch."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import lancedb
import requests
from lxml import etree
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from lex_retriever.embeddings import get_embedding_provider

from .indexer import LANCE_PATH, TABLE_NAME


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    reraise=True,
)
def _http_get(url: str) -> requests.Response:
    resp = requests.get(url, timeout=30, headers={"User-Agent": "lex-cases/1.0"})
    resp.raise_for_status()
    return resp


def _strip_ns(tag: str) -> str:
    return re.sub(r"^\{[^}]+\}", "", tag)


def _parse_xml_fulltext(content: bytes) -> str:
    """Extract Tatbestand + Entscheidungsgründe sections from XML."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return ""
    parts = []
    for target in ("tatbestand", "entscheidungsgruende", "gruende"):
        for elem in root.iter():
            if _strip_ns(elem.tag).lower() == target:
                text = " ".join(elem.itertext()).strip()
                if text:
                    parts.append(text)
    return "\n\n".join(parts)


def _parse_html_fulltext(content: bytes) -> str:
    """Extract Tatbestand + Entscheidungsgründe sections from HTML."""
    from lxml import html as lxml_html

    try:
        root = lxml_html.document_fromstring(content)
    except Exception:
        return ""

    if root is None:
        return ""

    for noise in root.xpath("//script | //style | //nav | //header | //footer"):
        parent = noise.getparent()
        if parent is not None:
            parent.remove(noise)

    sections: list[str] = []
    for keyword in ("Tatbestand", "Entscheidungsgründe", "Gründe", "Begründung"):
        nodes = root.xpath(
            f"//h1[contains(., '{keyword}')] | //h2[contains(., '{keyword}')] | "
            f"//h3[contains(., '{keyword}')] | //h4[contains(., '{keyword}')]"
        )
        for node in nodes:
            text_parts = [node.text_content().strip()]
            sibling = node.getnext()
            while sibling is not None:
                tag = getattr(sibling, "tag", "")
                if isinstance(tag, str) and tag in ("h1", "h2", "h3", "h4"):
                    break
                part = sibling.text_content().strip()
                if part:
                    text_parts.append(part)
                sibling = sibling.getnext()
            if len(text_parts) > 1:
                sections.append("\n".join(text_parts))

    if sections:
        return "\n\n".join(sections)

    texts = root.xpath("//text()")
    return " ".join(" ".join(t.split()) for t in texts if t.strip())


def _coerce_laws(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        return [s.strip() for s in raw.split("|") if s.strip()]
    try:
        return list(raw)
    except TypeError:
        return []


def _row_to_dict(row: dict, score: float | None = None) -> dict:
    result: dict = {
        "court":      row.get("court", ""),
        "az":         row.get("az", ""),
        "date":       row.get("date", ""),
        "type":       row.get("type", ""),
        "leitsatz":   row.get("leitsatz", row.get("text", "")),
        "laws_cited": _coerce_laws(row.get("laws_cited")),
        "url":        row.get("url", ""),
    }
    if score is not None:
        result["score"] = score
    return result


class LexCaseRetriever:
    def __init__(self, db_path: str = LANCE_PATH, embedding_provider=None):
        self.db = lancedb.connect(db_path)
        self.embedder = embedding_provider or get_embedding_provider()
        self._table = None

    def _get_table(self):
        if self._table is None:
            self._table = self.db.open_table(TABLE_NAME)
        return self._table

    def search(
        self,
        query: str,
        courts: list[str] | None = None,
        laws_cited: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """Semantic search over Leitsätze. Returns list of result dicts."""
        table = self._get_table()
        vector = self.embedder.embed([query])[0]

        # Over-fetch to allow post-filtering without losing top_k results
        candidates = (
            table
            .search(vector, vector_column_name="vector")
            .limit(top_k * 5)
            .to_list()
        )

        results: list[dict] = []
        seen_az: set[str] = set()

        for r in candidates:
            az = r.get("az", "")
            if az and az in seen_az:
                continue
            if az:
                seen_az.add(az)

            if courts and r.get("court") not in courts:
                continue

            if laws_cited:
                row_laws = _coerce_laws(r.get("laws_cited"))
                if not any(lc in row_laws for lc in laws_cited):
                    continue

            row_date = r.get("date", "")
            if date_from and row_date and row_date < date_from:
                continue
            if date_to and row_date and row_date > date_to:
                continue

            distance = r.get("_distance", 0.0)
            score = round(1.0 - (distance / 2), 4)
            results.append(_row_to_dict(r, score=score))

            if len(results) >= top_k:
                break

        return results

    def get_case_fulltext(self, url: str) -> str:
        """Live HTTP-fetch of Tatbestand + Gründe from rechtsprechung-im-internet.de."""
        resp = _http_get(url)
        content_type = resp.headers.get("Content-Type", "")
        if "xml" in content_type:
            return _parse_xml_fulltext(resp.content)
        return _parse_html_fulltext(resp.content)

    def get_cases_citing_law(self, law: str, paragraph: str) -> list[dict]:
        """Filter LanceDB by laws_cited containing e.g. '§ 280 BGB'."""
        search_str = f"{paragraph} {law}"
        table = self._get_table()
        rows = table.search().to_list()
        results: list[dict] = []
        seen_az: set[str] = set()
        for r in rows:
            az = r.get("az", "")
            if az and az in seen_az:
                continue
            row_laws = _coerce_laws(r.get("laws_cited"))
            if any(search_str in law_ref for law_ref in row_laws):
                if az:
                    seen_az.add(az)
                results.append(_row_to_dict(r))
        return results
