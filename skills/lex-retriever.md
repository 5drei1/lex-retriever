# Skill: lex-retriever

## What it does
`lex-retriever` performs **semantic search over indexed German law** paragraphs.
It returns the most relevant law passages for a given natural language query.

## When to use
- User asks a legal question about German law
- You need to cite specific paragraphs (§) from BGB, HGB, GmbHG, or GewO
- You need to verify legal requirements, obligations, or rights

## How to call

```python
from lex_retriever import search_law

results = search_law(
    query="Haftung des Geschäftsführers bei Insolvenz",
    laws=["GmbHG", "HGB"],  # optional filter
    top_k=5
)

for r in results:
    print(f"{r['law']} {r['paragraph']}: {r['text'][:200]}")
```

## Output format
Each result contains:
- `law` — Law abbreviation (e.g. "BGB")
- `paragraph` — Paragraph identifier (e.g. "§ 43")
- `text` — Full paragraph text
- `score` — Cosine similarity score (0–1, higher = more relevant)

## Available laws
| Code | Full name |
|---|---|
| BGB | Bürgerliches Gesetzbuch |
| HGB | Handelsgesetzbuch |
| GmbHG | GmbH-Gesetz |
| GewO | Gewerbeordnung |

## Adding more laws
Any agent or developer can add a new law by calling the indexer:
```python
from lex_retriever.indexer import index_law
index_law("GmbHG")  # re-indexes from provider
```
Or register a custom provider — see `providers/README.md`.

## Limitations
- Search is semantic, not keyword-exact — rephrase if results are off
- Only covers indexed laws (see table above)
- German-language queries perform best (multilingual model supports EN too)
