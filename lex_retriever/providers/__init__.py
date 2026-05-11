"""Law provider registry.

To add a new provider:
1. Create providers/my_provider.py implementing LawProvider
2. Import and add it to REGISTRY below
3. Done — no core code changes needed
"""

from .base import LawProvider
from .gesetze_im_internet import GesetzImInternetProvider
from .cellar_provider import CellarProvider
from .eur_lex import EurLexProvider  # kept for backwards compatibility; deprecated
from .neuris_provider import NeuRISProvider

REGISTRY: list[LawProvider] = [
    NeuRISProvider(),
    GesetzImInternetProvider(),
    CellarProvider(),
]


def get_providers_for_law(law_code: str) -> list[LawProvider]:
    """Return all registered providers that support the given law code."""
    return [p for p in REGISTRY if p.is_available(law_code)]


def all_supported_laws() -> list[str]:
    """Return deduplicated list of all law codes across all providers."""
    seen = set()
    result = []
    for p in REGISTRY:
        for law in p.supported_laws:
            key = law.upper()
            if key not in seen:
                seen.add(key)
                result.append(law)
    return result


__all__ = [
    "LawProvider",
    "GesetzImInternetProvider",
    "CellarProvider",
    "EurLexProvider",
    "NeuRISProvider",
    "REGISTRY",
    "get_providers_for_law",
    "all_supported_laws",
]
