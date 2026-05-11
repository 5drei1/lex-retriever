"""Case-law provider backed by the NeuRIS API (testphase.rechtsinformationen.bund.de).

Returns metadata-only dicts keyed by documentNumber; full text is fetched on demand
via NeuRISClient.get_case_law(documentNumber).
"""

from __future__ import annotations

import logging

from neuris import NeuRISClient
from neuris.transport import NeuRISTransport

from .base import CaseProvider

logger = logging.getLogger(__name__)

# Maps catalog key (uppercase) → NeuRIS court type code used in the API filter.
_COURT_CATALOG: dict[str, str] = {
    "BGH":    "BGH",
    "BVERFG": "BVerfG",
    "BAG":    "BAG",
    "BFH":    "BFH",
    "BVERWG": "BVerwG",
    "BPATG":  "BPatG",
}

_PAGE_SIZE = 100


class NeurisCasesProvider(CaseProvider):
    """Fetches German federal court decisions via the NeuRIS API.

    Only documentNumber and metadata are returned; no full text is stored.
    Pass a custom transport for testing or to target the production endpoint.
    """

    name = "neuris"
    supported_courts = list(_COURT_CATALOG)

    def __init__(self, transport: NeuRISTransport | None = None) -> None:
        self._transport = transport

    def fetch_court(self, court: str) -> list[dict]:
        """Return metadata dicts for all available decisions of the given court.

        Each dict contains: documentNumber, court, date, az, type, ecli, legal_effect.
        No full text is included; use NeuRISClient.get_case_law(documentNumber) for that.
        """
        code = court.upper()
        neuris_court = _COURT_CATALOG.get(code)
        if not neuris_court:
            raise ValueError(
                f"Court '{court}' not in catalog; supported: {list(_COURT_CATALOG)}"
            )

        client_kwargs: dict = {}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        results: list[dict] = []
        with NeuRISClient(**client_kwargs) as client:
            for search_result in client.search_case_law_iter(court=neuris_court, size=_PAGE_SIZE):
                decision = search_result.item
                az = decision.file_numbers[0] if decision.file_numbers else ""
                date_str = (
                    decision.decision_date.isoformat()
                    if decision.decision_date is not None
                    else ""
                )
                results.append({
                    "documentNumber": decision.document_number,
                    "court":          decision.court_label or decision.court_type,
                    "date":           date_str,
                    "az":             az,
                    "type":           decision.document_type,
                    "ecli":           decision.ecli or "",
                    "legal_effect":   decision.legal_effect or "",
                })

        logger.info("neuris: fetched %d decisions for %s", len(results), code)
        return results
