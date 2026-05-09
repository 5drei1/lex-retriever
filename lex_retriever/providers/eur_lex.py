"""EUR-Lex provider: fetches EU regulations from the EU Publications Office Cellar API."""

import re

import requests

from .base import LawProvider

# Direct Cellar document URLs (XHTML format, German language).
# Format: {cellar_id}.{version}/DOC_{n}
# Find via: publications.europa.eu/resource/cellar/{cellar_id} (with HTML Accept header)
_LAW_CELLAR_URLS = {
    "DSGVO": "http://publications.europa.eu/resource/cellar/3e485e15-11bd-11e6-ba9a-01aa75ed71a1.0004.03/DOC_1",
    # Add more EU regulations here — no core code changes needed
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; lex-retriever/1.0; +https://github.com/5drei1/lex-retriever)",
    "Accept": "application/xhtml+xml, text/html",
    "Accept-Language": "de-DE, de;q=0.9",
}


def _parse_cellar_xhtml(html: str, law_code: str) -> list[dict]:
    """Extract article chunks from the EU Publications Office XHTML format.

    The XHTML uses ELI (European Legislation Identifier) conventions:
    each article is a <div class="eli-subdivision" id="art_N"> element.
    """
    source = f"eur-lex.europa.eu/{law_code}"
    chunks = []

    article_pattern = re.compile(
        r'<div\s+class="eli-subdivision"\s+id="(art_\d+)"[^>]*>(.*?)'
        r'(?=<div\s+class="eli-subdivision"\s+id="art_\d+"|<div\s+class="eli-main|</body)',
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
            chunks.append({"paragraph": paragraph, "text": text, "source": source})

    return chunks


class EurLexProvider(LawProvider):
    """Fetches EU regulations from the EU Publications Office Cellar (German XHTML)."""

    name = "eur-lex"
    supported_laws = list(_LAW_CELLAR_URLS.keys())

    def fetch(self, law_code: str) -> list[dict]:
        url = _LAW_CELLAR_URLS.get(law_code.upper())
        if not url:
            raise ValueError(f"Law '{law_code}' not supported by {self.name}")
        response = requests.get(url, timeout=60, headers=_HEADERS)
        response.raise_for_status()
        return _parse_cellar_xhtml(response.text, law_code.upper())
