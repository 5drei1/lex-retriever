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

    def fetch_text(self, ref_id: str, paragraph: str) -> str:
        """Fetch text for a single paragraph on demand by its ref_id.

        Override in subclasses for efficient single-paragraph retrieval.
        Default returns empty string — subclasses should override.
        """
        return ""

    def available_laws(self) -> list[dict]:
        """Return ALL laws this provider can theoretically supply.

        Returns list of: { code, full_name, url }
        Default derives from supported_laws. Override for richer discovery.
        """
        return [{"code": law, "full_name": law, "url": ""} for law in self.supported_laws]

    def is_available(self, law_code: str) -> bool:
        """Check if this provider can supply the requested law."""
        return law_code.upper() in {e["code"].upper() for e in self.available_laws()}
