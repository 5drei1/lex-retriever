# lex-cases — Agent Interface

Semantic search and on-demand full-text retrieval over indexed German federal court decisions.

## Project Overview

**lex-cases** indexes decisions from [rechtsprechung-im-internet.de](https://www.rechtsprechung-im-internet.de), the official publication portal for German federal court decisions, and exposes them via a simple agent-callable API.

**Data source:** rechtsprechung-im-internet.de — bulk XML-ZIP downloads, publicly available, no authentication required, no rate limits documented.

**Supported courts:**

| Code | Full name |
|---|---|
| `BGH` | Bundesgerichtshof |
| `BVERFG` | Bundesverfassungsgericht |
| `BAG` | Bundesarbeitsgericht |
| `BFH` | Bundesfinanzhof |
| `BVERWG` | Bundesverwaltungsgericht |
| `BPATG` | Bundespatentgericht |

**Indexed content:** `<leitsatz>` (headnotes) and `<tenor>` (operative part) chunks — compact, semantically rich fragments of each decision.

---

## Available Functions

### search_case_law(query, courts, laws_cited, date_from, date_to, top_k)

Semantic search over indexed court decisions. Main entry point for unstructured legal queries.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | required | Natural language question or legal term (German or English) |
| `courts` | `list[str] \| None` | `None` | Filter by court codes, e.g. `["BGH", "BFH"]`; `None` = all courts |
| `laws_cited` | `list[str] \| None` | `None` | Filter to decisions citing these law codes, e.g. `["BGB", "HGB"]` |
| `date_from` | `str \| None` | `None` | Earliest decision date, ISO format `"YYYY-MM-DD"` |
| `date_to` | `str \| None` | `None` | Latest decision date, ISO format `"YYYY-MM-DD"` |
| `top_k` | `int` | `10` | Number of results to return |

**Returns:** `list[dict]`

| Key | Type | Description |
|---|---|---|
| `court` | `str` | Full court name, e.g. `"Bundesgerichtshof"` |
| `date` | `str` | Decision date, e.g. `"2024-01-15"` |
| `az` | `str` | Aktenzeichen (docket number), e.g. `"II ZR 123/23"` |
| `type` | `str` | Document type, e.g. `"Urteil"` or `"Beschluss"` |
| `laws_cited` | `list[dict]` | Cited law references: `[{"paragraph": "§ 280", "law": "BGB", "raw": "§ 280 BGB"}]` |
| `url` | `str` | Canonical URL on rechtsprechung-im-internet.de |
| `text` | `str` | Indexed chunk text (leitsatz or tenor) |
| `chunk_type` | `str` | `"leitsatz"` or `"tenor"` |
| `score` | `float` | Semantic similarity 0.0–1.0 (higher = more relevant) |

**Example:**

```python
from lex_cases import search_case_law

results = search_case_law(
    "Haftung des Geschäftsführers bei Insolvenz",
    courts=["BGH"],
    laws_cited=["GmbHG"],
    date_from="2020-01-01",
    top_k=5,
)
for r in results:
    print(r["az"], r["date"], r["score"])
    # II ZR 123/23  2024-01-15  0.8921
    print(r["text"][:120])
    print(r["url"])

# Full example result dict:
# {
#   "court": "Bundesgerichtshof",
#   "date": "2024-01-15",
#   "az": "II ZR 123/23",
#   "type": "Urteil",
#   "laws_cited": [{"paragraph": "§ 43", "law": "GmbHG", "raw": "§ 43 GmbHG"}],
#   "url": "https://www.rechtsprechung-im-internet.de/jportal/?docid=KORE123456789",
#   "text": "Der Geschäftsführer einer GmbH haftet der Gesellschaft gegenüber ...",
#   "chunk_type": "leitsatz",
#   "score": 0.8921,
# }
```

**When to use:** Default path for natural language questions about case law. Use `courts=` and `laws_cited=` filters to narrow results when you know the relevant court or statute.

Results are deduplicated by Aktenzeichen — each docket number appears at most once per result set.

---

### get_case_fulltext(url)

Fetch the full decision text on-demand directly from rechtsprechung-im-internet.de.

**Parameter:**

| Parameter | Type | Description |
|---|---|---|
| `url` | `str` | URL from a `search_case_law` result's `url` field |

**Returns:** `str` — full decision text, whitespace-normalised.

**When to use:** After `search_case_law` returns a relevant hit, call this to retrieve the full judgment text for detailed analysis, citation extraction, or summarisation. The index only stores `<leitsatz>` and `<tenor>` fragments; the full text is fetched on demand.

Retries up to 3 times on transient network errors with exponential backoff.

**No rate limits** are documented for rechtsprechung-im-internet.de, but be considerate — do not bulk-fetch fulltexts in a tight loop.

**Example:**

```python
from lex_cases import search_case_law, get_case_fulltext

results = search_case_law("Schadensersatz bei Vertragsverletzung", courts=["BGH"], top_k=3)
if results:
    fulltext = get_case_fulltext(results[0]["url"])
    print(fulltext[:500])
```

---

### get_cases_citing_law(law, paragraph)

Return all indexed decisions that cite a specific law paragraph.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `law` | `str` | Law abbreviation, e.g. `"BGB"` (case-insensitive) |
| `paragraph` | `str` | Paragraph identifier, e.g. `"§ 280"` |

**Returns:** `list[dict]` — same structure as `search_case_law` but without a `score` field.

**Example:**

```python
from lex_cases import get_cases_citing_law

cases = get_cases_citing_law("BGB", "§ 280")
print(f"{len(cases)} decisions cite BGB § 280")
for c in cases[:3]:
    print(c["az"], c["court"], c["date"])
```

**When to use:** When you need a comprehensive list of all decisions in the index citing a specific provision — e.g. to map how courts apply a particular paragraph.

---

## Rules for Agents

### When to use each function

| Situation | Function |
|---|---|
| Natural language legal question | `search_case_law(query)` |
| Question about a specific court | `search_case_law(query, courts=["BGH"])` |
| Question about decisions applying a statute | `search_case_law(query, laws_cited=["BGB"])` |
| "Which decisions cite § 280 BGB?" | `get_cases_citing_law("BGB", "§ 280")` |
| Read full judgment text after a search hit | `get_case_fulltext(result["url"])` |

### How to combine with lex-retriever

lex-retriever covers **statutory law** (BGB, HGB, GG, …); lex-cases covers **court decisions**.

Typical combined workflow:

```python
from lex_retriever import search_law
from lex_cases import search_case_law, get_case_fulltext

# Step 1: Find the relevant statutory provision
law_results = search_law("Haftung bei Vertragsverletzung", laws=["BGB"])
paragraph = law_results[0]["paragraph"]   # e.g. "§ 280"

# Step 2: Find decisions applying that provision
case_results = search_case_law(
    "Schadensersatz bei Leistungsstörung",
    courts=["BGH"],
    laws_cited=["BGB"],
)

# Step 3: Read the full text of the most relevant decision
if case_results:
    fulltext = get_case_fulltext(case_results[0]["url"])
```

### Rate-limit notes

rechtsprechung-im-internet.de publishes no documented rate limits. However:
- The bulk XML-ZIP download (used by the indexer) should be run infrequently.
- `get_case_fulltext` fetches individual pages; avoid calling it in tight loops.
- `search_case_law` and `get_cases_citing_law` query the local LanceDB index — no network calls.

---

## Setup

Install the package:

```bash
pip install -e .
```

Build the case law index (downloads XML-ZIPs from rechtsprechung-im-internet.de):

```bash
# Index one court
python -m lex_cases index BGH

# Index all supported courts
python -m lex_cases index-all
```

The index is written to `lancedb/german_cases.lance` in the repository root (configurable via `LEX_CASES_LANCE_PATH` env var).

---

## Error Handling

| Situation | Behaviour |
|---|---|
| No search results | Empty list `[]` — no error |
| Index not yet built | Exception on first DB access — run `python -m lex_cases index <COURT>` first |
| `get_case_fulltext` network error | Retried 3× with backoff; re-raises `requests.HTTPError` if all retries fail |
| Unknown court code | `ValueError` from the indexer — use one of `BGH BVERFG BAG BFH BVERWG BPATG` |
| `get_cases_citing_law` returns empty | No decisions cite that provision in the current index — re-index to get latest data |
