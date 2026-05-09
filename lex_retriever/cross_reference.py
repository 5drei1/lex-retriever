"""Cross-reference extractor and resolver for German legal texts."""

from __future__ import annotations

import re
from typing import Optional

# Captures: (full_match, base_number, optional_law_word)
# Handles: § 280, §§ 280, Art. 6, § 280 Abs. 1, §§ 280, 281 BGB, § 280 Abs. 1 BGB
_REF_PATTERN = re.compile(
    r"((?:§§?|Art\.?)\s*"
    r"(\d+\w*)"
    r"(?:,\s*\d+\w*)*"
    r"(?:\s+(?:Abs\.|Absatz)\s*\d+)?"
    r"(?:\s+([A-ZÄÖÜ][a-zA-ZÄÖÜäöüß]+))?)",
)

_LAW_ABBREVIATIONS = {
    "BGB", "HGB", "StGB", "ZPO", "GG", "DSGVO", "AGG", "GmbHG", "AktG",
    "UrhG", "MarkenG", "VVG", "SGB", "AO", "UStG", "EStG",
}


def extract_references(text: str, default_law: Optional[str] = None) -> list[dict]:
    """Extract all § and Art. references from a legal text.

    Returns:
        [{ "paragraph": "§ 280", "law": "BGB" or None, "raw": "§ 280 Abs. 1 BGB" }]
    """
    results = []
    for match in _REF_PATTERN.finditer(text):
        raw = match.group(1).strip()
        num = match.group(2)
        law_candidate = match.group(3)

        marker = "§" if "§" in raw else "Art."
        paragraph = f"{marker} {num}"

        law = None
        if law_candidate and law_candidate.upper() in _LAW_ABBREVIATIONS:
            law = law_candidate.upper()
        elif default_law:
            law = default_law.upper()

        results.append({"paragraph": paragraph, "law": law, "raw": raw})
    return results


def resolve_references(text: str, default_law: Optional[str] = None) -> list[dict]:
    """Extract references AND fetch their full text from the index.

    Returns:
        [{ "paragraph", "law", "raw", "text", "found": bool }]
    """
    from .tool import get_paragraph

    refs = extract_references(text, default_law)
    results = []
    for ref in refs:
        fetched = get_paragraph(ref["law"], ref["paragraph"]) if ref.get("law") else None
        results.append({
            **ref,
            "text": fetched["text"] if fetched else None,
            "found": fetched is not None,
        })
    return results
