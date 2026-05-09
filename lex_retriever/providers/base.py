from abc import ABC, abstractmethod


class LawProvider(ABC):
    """Abstract base class for all law data providers."""

    name: str
    supported_laws: list[str]

    @abstractmethod
    def fetch(self, law_code: str) -> list[dict]:
        """Download and parse law into chunks.

        Returns list of dicts: { paragraph, text, source }
        """

    def is_available(self, law_code: str) -> bool:
        """Check if this provider can supply the requested law."""
        return law_code.upper() in [l.upper() for l in self.supported_laws]
