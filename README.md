# lex-retriever

**Semantic search over German law** — a standalone, agent-callable tool powered by ChromaDB and sentence-transformers.

`lex-retriever` is not an agent itself. It is a callable tool that any agent (e.g. inside PaperclipAI) can invoke to perform semantic legal search over indexed German law paragraphs.

> **Extensible by design — no code changes required to add new laws.**
> Register a new `LawProvider` once → `index-all` picks it up automatically.
> Any website providing structured law text (XML, HTML, API) can be integrated.
> See [Adding a New Provider](#adding-a-new-provider).

---

## Supported Laws & Sources

### Default active laws (indexed by `index-all` without config)

| Law | Full Name | Source Website | Provider |
|---|---|---|---|
| BGB | Bürgerliches Gesetzbuch | [gesetze-im-internet.de](https://www.gesetze-im-internet.de/bgb/) | GesetzImInternetProvider |
| HGB | Handelsgesetzbuch | [gesetze-im-internet.de](https://www.gesetze-im-internet.de/hgb/) | GesetzImInternetProvider |
| GmbHG | GmbH-Gesetz | [gesetze-im-internet.de](https://www.gesetze-im-internet.de/gmbhg/) | GesetzImInternetProvider |
| GewO | Gewerbeordnung | [gesetze-im-internet.de](https://www.gesetze-im-internet.de/gewo/) | GesetzImInternetProvider |
| BDSG_2018 | Bundesdatenschutzgesetz | [gesetze-im-internet.de](https://www.gesetze-im-internet.de/bdsg_2018/) | GesetzImInternetProvider |
| DSGVO | Datenschutz-Grundverordnung (EU) | [eur-lex.europa.eu](https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:32016R0679) | EurLexProvider |

### Additional laws available for indexing (no code changes needed)

38 more German laws are catalogued and can be indexed on demand: StGB, ZPO, InsO, AktG, AGG, EStG, UrhG, GG, VwGO, VwVfG, KSchG, BetrVG, TzBfG, ArbZG, BUrlG, MuSchG, SGB I/II/V, StPO, JGG, GVG, StVG, UStG, WpHG, PatG, MarkenG, and more.

```bash
# See all downloadable laws grouped by provider
python -m lex_retriever list-available

# Index any law on demand
python -m lex_retriever index StGB
```

---

## Quick Start

```bash
# Core only (Python tool usage)
pip install -r requirements.txt

# With HTTP API (FastAPI server)
pip install -r requirements-api.txt

# Index all known laws at once (recommended)
python -m lex_retriever index-all

# Index a specific law
python -m lex_retriever index BGB

# List all available laws (no download)
python -m lex_retriever list-laws

# Search
python -c "
from lex_retriever import search_law
for r in search_law('Haftung bei Vertragsverletzung', top_k=3):
    print(r['law'], r['paragraph'], r['score'])
"
```

---

## CLI Reference

```
python -m lex_retriever index-all [--force]          # index active/default laws
python -m lex_retriever index <LAW_CODE> [--force]   # index a specific law
python -m lex_retriever list-laws                    # list default configured laws
python -m lex_retriever list-available               # list ALL downloadable laws
python -m lex_retriever status                       # show local DB state
```

### `list-available` — all downloadable laws per provider

```
[gesetze-im-internet]
  AKTG           Aktiengesetz                                        ✗ not indexed
  AGG            Allgemeines Gleichbehandlungsgesetz                 ✗ not indexed
  BGB            Bürgerliches Gesetzbuch                            ✓ indexed
  BDSG_2018      Bundesdatenschutzgesetz                            ✓ indexed
  ...

[eur-lex]
  DSGVO          Datenschutz-Grundverordnung (EU 2016/679)          ✓ indexed

Run: python -m lex_retriever index <LAW_CODE> to add a law to your DB.
```

### `status` — local DB overview

```
Local DB: ./chroma_db
Indexed laws: 5
  ✓ BGB            (3,098 chunks)
  ✓ HGB            (1,178 chunks)
  ✓ GMBHG          (163 chunks)
  ✓ GEWO           (387 chunks)
  ✓ DSGVO          (211 chunks)

Available but not indexed: 34 laws
Run `python -m lex_retriever list-available` to see all available laws.
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
│   ├── __main__.py          # CLI: python -m lex_retriever
│   ├── retriever.py         # ChromaDB search logic
│   ├── indexer.py           # indexes chunks from providers
│   ├── tool.py              # agent-callable tool wrapper + FastAPI
│   └── providers/
│       ├── __init__.py      # provider registry
│       ├── base.py          # LawProvider ABC
│       ├── gesetze_im_internet.py  # German federal law provider
│       └── eur_lex.py       # EU regulations provider (DSGVO)
├── chroma_db/               # persisted vector DB (git-ignored)
├── skills/
│   └── lex-retriever.md     # Agent Skill document
├── tests/
│   ├── test_retriever.py
│   ├── test_providers.py
│   └── test_cli.py
├── requirements.txt         # core dependencies
├── requirements-api.txt     # optional HTTP server extras
├── pyproject.toml
├── LICENSE
└── README.md
```

### Built-in Providers

| Provider class | Laws | Source |
|---|---|---|
| GesetzImInternetProvider | BGB, HGB, GmbHG, GewO, BDSG_2018 | gesetze-im-internet.de (XML-ZIP) |
| EurLexProvider | DSGVO | eur-lex.europa.eu (XML) |

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

3. Done — `index_law("STGB")` and `python -m lex_retriever index-all` automatically include it.

---

## Indexing

```python
from lex_retriever.indexer import index_law, index_all_laws

index_law("BGB")             # index one law
index_law("BGB", force=True) # re-index (overwrites existing)
index_all_laws()             # index ALL laws from ALL providers
```

---

## Configuration

### `lex_retriever.toml` (optional)

Place `lex_retriever.toml` in your working directory to control which laws are active and where the DB is stored. Copy `lex_retriever.toml.example` to get started:

```toml
[database]
path = "./chroma_db"

[laws]
# Only these laws will be indexed by `index-all`.
# Run `list-available` for all valid codes.
active = [
    "BGB",
    "HGB",
    "GMBHG",
    "DSGVO",
    "STGB",
]
```

Without a config file the default set (BGB, HGB, GmbHG, GewO, BDSG_2018) is used by `index-all`. Individual laws can always be indexed on demand with `index <LAW_CODE>` regardless of the config.

The `lex_retriever.toml` file is listed in `.gitignore` and is not committed to the repo.

### Environment variables

| Env var | Default | Description |
|---|---|---|
| CHROMA_PATH | ./chroma_db | Path to ChromaDB persistence directory |
| LEX_CONFIG | lex_retriever.toml | Path to TOML config file |

---

## Technical Details

- Embedding: pluggable provider (sentence-transformers default, Mistral, Google)
- Vector DB: ChromaDB (cosine similarity)
- German federal laws: gesetze-im-internet.de (XML-ZIP archives)
- EU regulations: eur-lex.europa.eu (Akoma Ntoso XML)
- Language support: German-primary, multilingual model supports EN queries

---

## Embedding Models

The embedding provider is configured in `lex_retriever.toml` and can be changed without any code modifications.

| Provider | Model | Token Limit | Dimensions | Cost |
|---|---|---|---|---|
| sentence-transformers | `paraphrase-multilingual-MiniLM-L12-v2` | ⚠️ 128 | 384 | free, local |
| Mistral | `mistral-embed` | 8,192 | 1,024 | $0.10/1M tokens |
| Google | `text-embedding-004` | 2,048 | 768 | **free tier** |

> 💡 **Google API Key (free, no credit card required):**
> [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

> ⚠️ **Provider change requires re-indexing.** If you switch providers, run:
> `python -m lex_retriever index-all --force`
> The tool warns you on the next index operation if the stored provider differs from your config.

### sentence-transformers (default)

No API key needed. The model (~470 MB) is downloaded automatically from HuggingFace on first use.

```toml
[embedding]
provider = "sentence-transformers"
model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

> ⚠️ **128-token limit:** Long paragraphs are automatically split into overlapping chunks — no manual action needed.

### Mistral

```bash
pip install mistralai
export MISTRAL_API_KEY="your-key"
```

```toml
[embedding]
provider = "mistral"
model = "mistral-embed"
api_key_env = "MISTRAL_API_KEY"
```

### Google Gemini

```bash
pip install google-generativeai
export GOOGLE_API_KEY="your-key"
```

```toml
[embedding]
provider = "google"
model = "text-embedding-004"
api_key_env = "GOOGLE_API_KEY"
```

---

## Running Tests

```bash
pip install pytest

# Run all tests (retriever tests skipped if chroma_db/ not populated)
pytest tests/ -v

# Run only unit tests (skip DB-dependent tests)
pytest -m "not requires_db" -v

# Run DB-dependent tests only (requires populated chroma_db/)
python -m lex_retriever index-all
pytest -m "requires_db" -v
```

> `chroma_db/` is excluded from version control. Run `python -m lex_retriever index-all` to populate it locally.

---

## License

MIT — see LICENSE.
