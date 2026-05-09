"""Static query expansion for German legal terminology."""

from __future__ import annotations

LEGAL_SYNONYMS: dict[str, list[str]] = {
    "haftung": ["schadensersatz", "pflichtverletzung", "verantwortung"],
    "schaden": ["schadensersatz", "nachteil", "verlust"],
    "kündigung": ["außerordentliche kündigung", "fristlose kündigung", "beendigung"],
    "vertrag": ["vertragspflicht", "vertragsschluss", "vereinbarung"],
    "miete": ["mietvertrag", "mietzins", "mietverhältnis"],
    "eigentum": ["eigentumsrecht", "eigentumsübertragung", "besitz"],
    "schuld": ["schuldner", "schuldverhältnis", "verbindlichkeit"],
    "anspruch": ["forderung", "rechtsanspruch", "klagerecht"],
    "pflicht": ["verpflichtung", "obliegenheit", "sorgfaltspflicht"],
    "strafe": ["bußgeld", "sanktion", "freiheitsstrafe"],
    "erbrecht": ["erbe", "erbfolge", "nachlass"],
    "gewährleistung": ["mängelrecht", "nacherfüllung", "rücktritt"],
}


def expand_query(query: str) -> str:
    """Expand query with legal synonyms.

    Original query is preserved as the leading part; synonyms are appended.
    Uses substring matching so compound words like "Vertragsstrafe" trigger
    synonyms for both "vertrag" and "strafe".
    Returns the original query unchanged when no known terms are found.
    """
    query_lower = query.lower()
    expansions: list[str] = []
    for term, synonyms in LEGAL_SYNONYMS.items():
        if term in query_lower:
            expansions.extend(synonyms)
    if expansions:
        seen: set[str] = set()
        unique = [x for x in expansions if not (x in seen or seen.add(x))]
        return f"{query} {' '.join(unique)}"
    return query
