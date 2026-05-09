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
    Returns the original query unchanged when no known terms are found.
    """
    words = query.lower().split()
    expansions: list[str] = []
    for word in words:
        if word in LEGAL_SYNONYMS:
            expansions.extend(LEGAL_SYNONYMS[word])
    if expansions:
        return f"{query} {' '.join(expansions)}"
    return query
