from abc import ABC, abstractmethod


class CaseProvider(ABC):
    @abstractmethod
    def fetch_court(self, court: str) -> list[dict]:
        """Return list of case dicts for the given court."""
        ...
