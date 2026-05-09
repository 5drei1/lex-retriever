# lex-retriever — Agent Interface

Semantic search and full-text retrieval over indexed German federal law paragraphs.

## Verfügbare Funktionen

### search_law(query, laws, top_k)

Semantic search using embedding similarity. Main entry point for unstructured legal queries.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | required | Natural language question or legal term (German or English) |
| `laws` | `list[str] \| None` | `None` | Filter by law codes, e.g. `["BGB", "HGB"]`; `None` = search all indexed laws |
| `top_k` | `int` | `10` | Number of results to return |

**Returns:** `list[dict]`

| Key | Type | Description |
|---|---|---|
| `law` | `str` | Law abbreviation, e.g. `"BGB"` |
| `paragraph` | `str` | Paragraph identifier, e.g. `"§ 280"` |
| `text` | `str` | Full paragraph text |
| `score` | `float` | Similarity score 0.0–1.0 (higher = more relevant) |
| `original_query` | `str` | The query string that produced this result |

**Example:**
```python
from lex_retriever import search_law

results = search_law(
    "Haftung des Geschäftsführers bei Insolvenz",
    laws=["GmbHG", "HGB"],
    top_k=5,
)
for r in results:
    print(r["law"], r["paragraph"], r["score"])
    # GmbHG § 43 0.9123
```

**When to use:** Default path when you have a natural language question and do not know the exact paragraph number.

---

### get_paragraph(law, paragraph)

Retrieve a specific paragraph by exact law + paragraph identifier. Faster and more precise than semantic search when the paragraph number is known.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `law` | `str` | Law abbreviation, e.g. `"BGB"` (case-insensitive) |
| `paragraph` | `str` | Paragraph identifier, e.g. `"§ 280"` or `"Art. 6"` |

**Returns:** `dict | None`

| Key | Type | Description |
|---|---|---|
| `law` | `str` | Law abbreviation (uppercased) |
| `paragraph` | `str` | Paragraph identifier |
| `text` | `str` | Full concatenated paragraph text |
| `chunks` | `int` | Number of index chunks merged into the result |

Returns `None` if the paragraph is not in the index.

**Example:**
```python
from lex_retriever.tool import get_paragraph

result = get_paragraph("BGB", "§ 280")
if result:
    print(result["text"])
```

**When to use:** Prefer over `search_law` whenever the exact paragraph number is known.

---

### get_full_law(law, offset, limit)

Return all indexed paragraphs of a law, paginated.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `law` | `str` | required | Law abbreviation, e.g. `"BGB"` |
| `offset` | `int` | `0` | Paragraph offset for pagination |
| `limit` | `int` | `50` | Max paragraphs per page |

**Returns:** `dict`

| Key | Type | Description |
|---|---|---|
| `law` | `str` | Law abbreviation |
| `total_paragraphs` | `int` | Total number of indexed paragraphs in this law |
| `offset` | `int` | Current page offset |
| `paragraphs` | `list[dict]` | List of `{"paragraph": str, "text": str}` |

**Pagination example:**
```python
from lex_retriever.tool import get_full_law

page = get_full_law("BGB", offset=0, limit=50)
total = page["total_paragraphs"]

while page["offset"] < total:
    for p in page["paragraphs"]:
        print(p["paragraph"], p["text"][:80])
    next_offset = page["offset"] + len(page["paragraphs"])
    if next_offset >= total:
        break
    page = get_full_law("BGB", offset=next_offset, limit=50)
```

---

### resolve_references(text, default_law)

Extract all `§` and `Art.` references from a text and fetch their full paragraph text from the index in one call.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `text` | `str` | Legal text containing references like `"§ 280 BGB"` or `"Art. 6 DSGVO"` |
| `default_law` | `str \| None` | Fallback law when a reference has no explicit law abbreviation |

**Returns:** `list[dict]`

| Key | Type | Description |
|---|---|---|
| `paragraph` | `str` | Extracted paragraph id, e.g. `"§ 280"` |
| `law` | `str \| None` | Resolved law abbreviation; `None` if unresolvable |
| `raw` | `str` | Original reference string from the input text |
| `text` | `str \| None` | Full paragraph text from the index; `None` if not found |
| `found` | `bool` | `True` if the paragraph was retrieved from the index |

**Example:**
```python
from lex_retriever.cross_reference import resolve_references

refs = resolve_references(
    "Der Schuldner haftet nach § 280 BGB auf Schadensersatz.",
    default_law="BGB",
)
# refs[0]:
# {
#   "paragraph": "§ 280",
#   "law": "BGB",
#   "raw": "§ 280 BGB",
#   "text": "Verletzt der Schuldner eine Pflicht aus dem Schuldverhältnis ...",
#   "found": True,
# }
```

---

## HTTP API

Start the server (requires `requirements-api.txt`):
```bash
pip install -r requirements-api.txt
uvicorn lex_retriever.tool:app --host 0.0.0.0 --port 8000
```

Base URL: `http://localhost:8000`

### POST /search

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Haftung bei Vertragsverletzung", "laws": ["BGB"], "top_k": 5}'
```

Request body: `{"query": str, "laws": list[str] | null, "top_k": int}`
Response: same schema as `search_law()`

### GET /paragraph/{law}/{paragraph}

```bash
curl "http://localhost:8000/paragraph/BGB/%C2%A7%20280"
```

Response: same schema as `get_paragraph()`. Returns HTTP 404 if not found.

### GET /law/{law}

```bash
curl "http://localhost:8000/law/BGB?offset=0&limit=50"
```

Query params: `offset: int = 0`, `limit: int = 50`
Response: same schema as `get_full_law()`

### POST /resolve-references

```bash
curl -X POST http://localhost:8000/resolve-references \
  -H "Content-Type: application/json" \
  -d '{"text": "Gemäß § 280 BGB haftet der Schuldner...", "default_law": "BGB"}'
```

Request body: `{"text": str, "default_law": str | null}`
Response: same schema as `resolve_references()`

### GET /health

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

---

## Wichtige Regeln für Agenten

- **Index muss lokal vorhanden sein** — `python -m lex_retriever index BGB` (einzelnes Gesetz) oder `index-all` (alle Standard-Gesetze). Ohne Index schlägt der erste DB-Zugriff fehl.
- **`score` ∈ `[0.0, 1.0]`** — höher ist relevanter; Ergebnisse unter 0.5 sind oft nicht einschlägig.
- **`laws=[...]` immer setzen wenn das Gesetz bekannt ist** — erhöht Präzision und Geschwindigkeit deutlich.
- **`get_paragraph()` bevorzugen wenn die Paragraphennummer bekannt ist** — präziser als Semantic Search.
- **`resolve_references()` für automatisches Follow-up von Querverweisen** — extrahiert und lädt alle `§`/`Art.`-Referenzen in einem Aufruf.
- **Law-Codes sind case-insensitive** — `"bgb"` und `"BGB"` sind äquivalent; intern wird uppercase normalisiert.

---

## Bekannte Einschränkungen

- Nur deutsche Bundesgesetze + DSGVO — keine Landesgesetze, keine Urteile, keine Verwaltungsvorschriften.
- Kein Volltext-Abruf von Gerichtsentscheidungen (geplant für lex-cases).
- Index muss nach Gesetzesänderungen manuell neu aufgebaut werden: `python -m lex_retriever index <LAW> --force`.
- Wechsel des Embedding-Providers erfordert vollständigen Re-Index aller Gesetze.

---

## Fehlerbehandlung

| Situation | Verhalten |
|---|---|
| Keine Suchergebnisse | Leere Liste `[]` — kein Fehler |
| Paragraph nicht indexiert | `get_paragraph()` gibt `None` zurück |
| Unbekannter Law-Code | `ValueError` — `python -m lex_retriever list-available` prüfen |
| Index nicht vorhanden | Exception beim ersten DB-Zugriff — zuerst indexieren |

```python
result = get_paragraph("BGB", "§ 999")
if result is None:
    # Paragraph nicht indexiert — Fallback auf Semantic Search
    results = search_law("§ 999 BGB", laws=["BGB"])
```
