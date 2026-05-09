# lex-retriever

**Semantic search over German law** — a standalone, agent-callable tool powered by ChromaDB and sentence-transformers.

`lex-retriever` is not an agent itself. It is a callable tool that any agent (e.g. inside PaperclipAI) can invoke to perform semantic legal search over indexed German law paragraphs.

---

## Quick Start

```bash
# Core only (Python tool usage)
pip install -r requirements.txt

# With HTTP API (FastAPI server)
pip install -r requirements-api.txt

# Index laws (downloads from gesetze-im-internet.de)
# Note: chroma_db/ is excluded from version control — you must build it locally
python -c "from lex_retriever.indexer import index_law; index_law('BGB')"

# Search
python -c "
from lex_retriever import search_law
for r in search_law('Haftung bei Vertragsverletzung', top_k=3):
    print(r['law'], r['paragraph'], r['score'])
"
```

---

## Tool Interface

```python
from lex_retriever import search_law

results = search_law(
    query="Haftung des Geschäftsführers bei Insolvenz",
    laws=["GmbHG", "HGB"],  # optional filter; None = search all
    top_k=5
)

for r in results:
    print(f"{r['law']} {r['paragraph']}: {r['text'][:200]}")
```

### Return format

Each result is a dict with:

| Key | Type | Description |
|---|---|---|
| `law` | str | Law abbreviation (e.g. "BGB") |
| `paragraph` | str | Paragraph identifier (e.g. "§ 43") |
| `text` | str | Full paragraph text |
| `score` | float | Cosine similarity (0–1, higher = more relevant) |

---

## HTTP API (optional)

Start the FastAPI server:

```bash
uvicorn lex_retriever.tool:app --host 0.0.0.0 --port 8000
```

Endpoint: `POST /search`

```json
{
  "query": "Vertragspflichten",
  "laws": ["BGB"],
  "top_k": 5
}
```

---

## Architecture

### Law-Provider Architecture

Law sources are **pluggable Provider classes** implementing a common interface. Adding a new source requires no changes to core code.

```
lex-retriever/
├── lex_retriever/
│   ├── __init__.py          # exports search_law()
│   ├── retriever.py         # ChromaDB search logic
│   ├── indexer.py           # indexes chunks from providers
│   ├── tool.py              # agent-callable tool wrapper + FastAPI
│   └── providers/
│       ├── __init__.py      # provider registry
│       ├── base.py          # LawProvider ABC
│       └── gesetze_im_internet.py  # built-in provider
├── chroma_db/               # persisted vector DB (git-ignored)
├── skills/
│   └── lex-retriever.md     # Agent Skill document
├── tests/
│   ├── test_retriever.py
│   └── test_providers.py
├── requirements.txt         # core dependencies
├── requirements-api.txt     # optional HTTP server extras
├── pyproject.toml
├── LICENSE
└── README.md
```

### Built-in Providers

| Provider class | Laws | Source |
|---|---|---|
| GesetzImInternetProvider | BGB, HGB, GmbHG, GewO | gesetze-im-internet.de (XML-ZIP) |

### Adding a New Provider

1. Create `lex_retriever/providers/my_provider.py`:

```python
from .base import LawProvider

class MyProvider(LawProvider):
    name = "my-source"
    supported_laws = ["STGB"]

    def fetch(self, law_code: str) -> list[dict]:
        # Return list of: { paragraph, text, source }
        ...
```

2. Register in `lex_retriever/providers/__init__.py`:

```python
from .my_provider import MyProvider
REGISTRY.append(MyProvider())
```

3. Done — `index_law("STGB")` will now use your provider.

---

## Available Laws

| Code | Full name |
|---|---|
| BGB | Bürgerliches Gesetzbuch |
| HGB | Handelsgesetzbuch |
| GmbHG | GmbH-Gesetz |
| GewO | Gewerbeordnung |

---

## Indexing

```python
from lex_retriever.indexer import index_law, index_all_laws

index_law("BGB")             # index one law
index_law("BGB", force=True) # re-index (overwrites existing)
index_all_laws()             # index all supported laws
```

---

## Configuration

| Env var | Default | Description |
|---|---|---|
| CHROMA_PATH | ./chroma_db | Path to ChromaDB persistence directory |

---

## Technical Details

- Embedding model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- Vector DB: ChromaDB (cosine similarity)
- Law source: gesetze-im-internet.de (XML-ZIP archives)
- Language support: German-primary, multilingual model supports EN queries

---

## Running Tests

```bash
pip install pytest

# Run all tests (retriever tests skipped if chroma_db/ not populated)
pytest tests/ -v

# Run only unit tests (skip DB-dependent tests)
pytest -m "not requires_db" -v

# Run DB-dependent tests only (requires populated chroma_db/)
python -c "from lex_retriever.indexer import index_law; index_law('BGB')"
pytest -m "requires_db" -v
```

> `chroma_db/` is excluded from version control. Run `index_law("BGB")` (or `index_all_laws()`) to populate it locally.

---

## License

MIT — see LICENSE.
