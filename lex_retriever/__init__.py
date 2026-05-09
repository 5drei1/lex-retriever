"""lex-retriever: semantic search over indexed German law paragraphs."""

from .tool import search_law
from .indexer import index_law, index_all_laws

__all__ = ["search_law", "index_law", "index_all_laws"]
__version__ = "0.1.0"
