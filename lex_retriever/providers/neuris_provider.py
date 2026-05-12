"""NeuRIS law provider — fetches German federal legislation via neuris-python."""

from __future__ import annotations

import re
from typing import Any

from neuris import NeuRISClient
from neuris.exceptions import NeuRISError, NeuRISNotFoundError
from neuris.transport import NeuRISTransport, TestphaseTransport

from .base import LawProvider

_WS_RE = re.compile(r"\s+")


def _itertext(value: str) -> str:
    """Return whitespace-normalized text, stripping markup when present."""
    if "<" not in value and ">" not in value:
        return value.strip()
    try:
        from lxml import html as lxml_html
        root = lxml_html.fromstring(value)
        return _WS_RE.sub(" ", " ".join(root.itertext())).strip()
    except Exception:
        return _WS_RE.sub(" ", re.sub(r"<[^>]+>", " ", value)).strip()


def _eli_path(eli: str) -> str:
    """Extract API path payload from an ELI identifier or URL."""
    stripped = eli.strip()
    if "/eli/" in stripped:
        stripped = stripped.split("/eli/", 1)[1]
    stripped = stripped.lstrip("/")
    if stripped.startswith("eli/"):
        stripped = stripped[4:]
    return stripped


def _normalize_eli_url(eli: str) -> str:
    """Return a canonical HTTPS ELI URL."""
    stripped = eli.strip()
    if not stripped:
        return stripped
    if stripped.startswith("http://") or stripped.startswith("https://"):
        return stripped
    stripped = stripped.lstrip("/")
    if not stripped.startswith("eli/"):
        stripped = f"eli/{stripped}"
    return f"https://testphase.rechtsinformationen.bund.de/{stripped}"


def _extract_text(raw: dict[str, Any]) -> str:
    """Extract text content from a raw NeuRIS legislation part response.

    Tries multiple field names because the testphase API schema is not yet stable.
    Falls back to official_long_title or name as a last resort.
    """
    for field in ("text", "content", "htmlText", "normtext", "body"):
        val = raw.get(field)
        if val and isinstance(val, str):
            return _itertext(val)
    # Nested structure: some responses wrap text in a sub-object
    for field in ("textContent", "articleContent", "legislationText"):
        nested = raw.get(field)
        if isinstance(nested, dict):
            for sub in ("text", "content", "value"):
                val = nested.get(sub)
                if val and isinstance(val, str):
                    return _itertext(val)
    # Last resort: the official long title contains substantive description
    return (raw.get("officialLongTitle") or "").strip()


class NeuRISProvider(LawProvider):
    """Fetches German federal legislation from the NeuRIS testphase API.

    Uses neuris-python as the HTTP client. The `source` field in returned
    chunks is the ELI (European Legislation Identifier) of the law part.

    Coverage scope:
        NeuRIS (testphase.rechtsinformationen.bund.de) covers only laws
        published through the digital Bundesgesetzblatt (BGBl) system.
        Classical German codifications that predate BGBl digitisation — such
        as BGB, HGB, or StGB — are **not** available here.  Use
        ``GesetzImInternetProvider`` for those laws instead.

        ``supported_laws = []`` is intentional: this is a dynamic provider
        that calls ``is_available()`` against the live API rather than
        maintaining a static allowlist.

    Args:
        transport: Optional NeuRISTransport for testing/overriding.
                   Defaults to TestphaseTransport (live testphase API).
    """

    name = "neuris"
    supported_laws: list[str] = []  # dynamic — is_available queries the API

    def __init__(self, transport: NeuRISTransport | None = None) -> None:
        self._transport = transport or TestphaseTransport()
        self._client = NeuRISClient(transport=self._transport)

    def is_available(self, law_code: str) -> bool:
        """Check availability by searching NeuRIS for an exact abbreviation match."""
        try:
            page = self._client.search_legislation(search_term=law_code, size=10)
            for result in page.members:
                if result.item.abbreviation.upper() == law_code.upper():
                    return True
        except NeuRISError:
            pass
        return False

    def available_laws(self) -> list[dict]:
        """Return all laws known to NeuRIS (auto-paginated)."""
        laws: list[dict] = []
        seen: set[str] = set()
        try:
            for result in self._client.search_legislation_iter():
                item = result.item
                key = item.abbreviation.upper()
                if key and key not in seen:
                    seen.add(key)
                    laws.append({
                        "code": item.abbreviation,
                        "full_name": item.name,
                        "url": _normalize_eli_url(item.legislation_identifier),
                    })
        except NeuRISError:
            pass
        return laws

    def fetch(self, law_code: str) -> list[dict]:
        """Fetch all paragraph chunks for the given law code.

        Returns:
            List of dicts with keys: paragraph, text, source (ELI).

        Raises:
            ValueError: If the law is not found in NeuRIS.
        """
        code = law_code.upper()

        # Step 1: find the law by abbreviation
        page = self._client.search_legislation(search_term=law_code, size=20)
        law = None
        for result in page.members:
            if result.item.abbreviation.upper() == code:
                law = result.item
                break

        if law is None:
            raise ValueError(f"Law '{law_code}' not found in NeuRIS")

        # Step 2: fetch the full legislation record to get all parts
        try:
            full_law = self._client.get_legislation_by_eli(law.legislation_identifier)
        except NeuRISNotFoundError:
            full_law = law

        # Step 3: for each part, fetch raw data and extract text
        chunks: list[dict] = []
        for part in full_law.has_part:
            part_eli = getattr(part, "eli", None)
            if not part_eli:
                continue
            try:
                raw = self._transport.get(f"/legislation/eli/{_eli_path(part_eli)}")
            except NeuRISError:
                continue

            text = _extract_text(raw)
            if not text:
                continue

            # Use the last ELI segment as the paragraph identifier
            paragraph = raw.get("name") or raw.get("abbreviation") or part.eli.split("/")[-1]
            if not raw.get("name") and not raw.get("abbreviation"):
                paragraph = part_eli.split("/")[-1]

            chunks.append({
                "paragraph": str(paragraph),
                "text": text,
                "source": _normalize_eli_url(part_eli),
            })

        return chunks

    def fetch_text(self, ref_id: str, paragraph: str) -> str:
        # ref_id is the ELI of the specific legislation part
        try:
            raw = self._transport.get(f"/legislation/eli/{_eli_path(ref_id)}")
            return _extract_text(raw)
        except NeuRISError:
            return ""
