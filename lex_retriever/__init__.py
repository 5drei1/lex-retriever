"""lex-retriever: semantic search over indexed German law paragraphs."""

from .tool import search_law, get_full_law, get_paragraph
from .indexer import index_law, index_all_laws
from .cross_reference import extract_references, resolve_references

__all__ = [
    "search_law",
    "get_full_law",
    "get_paragraph",
    "index_law",
    "index_all_laws",
    "extract_references",
    "resolve_references",
]
__version__ = "0.1.0"
