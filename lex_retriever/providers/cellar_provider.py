"""CELLAR/SPARQL provider: fetches EU legislation by CELEX number."""

import re

import requests

try:
    from SPARQLWrapper import JSON, SPARQLWrapper
except ImportError:
    SPARQLWrapper = None  # type: ignore[assignment,misc]
    JSON = None  # type: ignore[assignment]

from .base import LawProvider

SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"
_CDM = "http://publications.europa.eu/ontology/cdm#"

_CELEX_MAP: dict[str, str] = {
    "DSGVO": "32016R0679",
    "NIS2": "32022L2555",
    "AI_ACT": "32024R1689",
    "DSA": "32022R2065",
    "DMA": "32022R1925",
}

_FULL_NAMES: dict[str, str] = {
    "DSGVO": "Datenschutz-Grundverordnung (EU 2016/679)",
    "NIS2": "NIS2-Richtlinie (EU 2022/2555)",
    "AI_ACT": "KI-Verordnung (EU 2024/1689)",
    "DSA": "Gesetz über digitale Dienste (EU 2022/2065)",
    "DMA": "Gesetz über digitale Märkte (EU 2022/1925)",
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; lex-retriever/1.0; +https://github.com/5drei1/lex-retriever)",
    "Accept": "application/xhtml+xml, text/html",
    "Accept-Language": "de-DE, de;q=0.9",
}


def _resolve_cellar_uri(celex_number: str) -> str | None:
    """Query CELLAR SPARQL to resolve a CELEX number to its work URI."""
    if SPARQLWrapper is None:
        return None
    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setTimeout(30)
    sparql.setQuery(
        "PREFIX cdm: <" + _CDM + ">\n"
        "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"
        "SELECT DISTINCT ?work WHERE {\n"
        "  ?work cdm:resource_legal_id_celex \"" + celex_number + "\"^^xsd:string .\n"
        "} LIMIT 1"
    )
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    bindings = results.get("results", {}).get("bindings", [])
    return bindings[0]["work"]["value"] if bindings else None


def _fallback_url(celex_number: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:{celex_number}"


def _parse_cellar_html(html: str, celex_number: str) -> list[dict]:
    """Extract article chunks from EUR-Lex HTML/XHTML. Source field is the CELEX number."""
    chunks = []

    article_pattern = re.compile(
        r'<div[^>]+id="(art_\d+)"[^>]*>(.*?)'
        r'(?=<div[^>]+id="art_\d+"|</body)',
        re.DOTALL,
    )

    for m in article_pattern.finditer(html):
        art_id = m.group(1)
        art_html = m.group(2)
        art_num = art_id.replace("art_", "")

        heading_m = re.search(
            r'class="[^"]*oj-doc-ti[^"]*"[^>]*>(.*?)</p>', art_html, re.DOTALL
        )
        heading = ""
        if heading_m:
            heading = re.sub(r"<[^>]+>", "", heading_m.group(1)).strip()

        text = re.sub(r"<[^>]+>", " ", art_html)
        text = re.sub(r"\s+", " ", text).strip()

        paragraph = f"Artikel {art_num}"
        if heading:
            paragraph = f"{paragraph} — {heading}"

        if text:
            chunks.append({"paragraph": paragraph, "text": text, "source": celex_number})

    return chunks


class CellarProvider(LawProvider):
    """Fetches EU legislation from EUR-Lex/CELLAR by CELEX number via SPARQL discovery."""

    name = "cellar"
    supported_laws = list(_CELEX_MAP.keys())

    def available_laws(self) -> list[dict]:
        return [
            {
                "code": code,
                "full_name": _FULL_NAMES.get(code, code),
                "url": _fallback_url(_CELEX_MAP[code]),
            }
            for code in sorted(_CELEX_MAP.keys())
        ]

    def fetch(self, law_code: str) -> list[dict]:
        code = law_code.upper()
        celex = _CELEX_MAP.get(code)
        if not celex:
            raise ValueError(f"Law '{law_code}' not supported by {self.name}")

        # SPARQL resolves the canonical Cellar work URI; fall back to EUR-Lex URL if unavailable.
        try:
            work_uri = _resolve_cellar_uri(celex)
        except Exception:
            work_uri = None

        url = work_uri if work_uri else _fallback_url(celex)
        response = requests.get(url, timeout=60, headers=_HEADERS)
        response.raise_for_status()
        return _parse_cellar_html(response.text, celex)

    def fetch_text(self, ref_id: str, paragraph: str) -> str:
        # ref_id is the CELEX number (same for all articles of a regulation)
        try:
            law_code = next((k for k, v in _CELEX_MAP.items() if v == ref_id), None)
            if not law_code:
                return ""
            for chunk in self.fetch(law_code):
                if chunk["paragraph"] == paragraph:
                    return chunk["text"]
        except Exception:
            pass
        return ""
