"""Agent-callable interface for lex-cases case law retrieval."""

from .retriever import LexCaseRetriever

_retriever: LexCaseRetriever | None = None


def _get_retriever() -> LexCaseRetriever:
    global _retriever
    if _retriever is None:
        _retriever = LexCaseRetriever()
    return _retriever


def search_case_law(
    query: str,
    courts: list[str] | None = None,
    laws_cited: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    top_k: int = 10,
) -> list[dict]:
    """Search German court decisions semantically."""
    return _get_retriever().search(query, courts=courts, laws_cited=laws_cited,
                                   date_from=date_from, date_to=date_to, top_k=top_k)


def get_case_fulltext(url: str) -> str:
    """Fetch full decision text on-demand from rechtsprechung-im-internet.de."""
    return _get_retriever().get_case_fulltext(url)


def get_cases_citing_law(law: str, paragraph: str) -> list[dict]:
    """Return all indexed cases citing a specific law paragraph."""
    return _get_retriever().get_cases_citing_law(law, paragraph)
