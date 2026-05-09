# lex-retriever

Durchsuche deutsche Gesetze auf Knopfdruck — stell eine Frage in natürlicher Sprache, bekomme die relevanten Paragraphen zurück.

Gedacht für **Entwickler, Anwälte, Juristen und Legal-Tech-Anwendungen** die schnell und programmatisch auf Gesetzestexte zugreifen wollen, ohne selbst Datenbanken zu pflegen.

> **Extensible by design — no code changes required to add new laws.**
> Register a new `LawProvider` once → `index-all` picks it up automatically.

---

## Was kann ich damit machen?

```python
from lex_retriever import search_law

# Semantische Suche — keine exakte Paragraphennummer nötig
results = search_law("Haftung bei Vertragsverletzung", laws=["BGB"], top_k=3)
for r in results:
    print(r["law"], r["paragraph"], r["score"])
    # BGB § 280  0.91
```

```python
from lex_retriever.tool import get_paragraph

# Direktabruf wenn die Paragraphennummer bekannt ist
para = get_paragraph("BGB", "§ 280")
print(para["text"])  # "Verletzt der Schuldner eine Pflicht ..."
```

```python
from lex_retriever.cross_reference import resolve_references

# Alle §-Referenzen in einem Text automatisch auflösen
refs = resolve_references("Der Schuldner haftet nach § 280 BGB.", default_law="BGB")
print(refs[0]["text"])  # Volltext von § 280 BGB
```

```python
from lex_retriever.tool import get_full_law

# Ganzes Gesetz paginiert abrufen
page = get_full_law("DSGVO", offset=0, limit=20)
print(f"{page['total_paragraphs']} Paragraphen insgesamt")
```

---

## Schnellstart

```bash
pip install -r requirements.txt
python -m lex_retriever index-all        # Index aufbauen (einmalig)
python -m lex_retriever list-laws        # verfügbare Gesetze anzeigen
python -c "from lex_retriever import search_law; print(search_law('Kündigung fristlos', laws=['BGB'], top_k=3))"
```

---

## Welche Gesetze sind enthalten?

### Standard-Gesetze (werden von `index-all` automatisch indexiert)

| Kürzel | Vollname |
|---|---|
| BGB | Bürgerliches Gesetzbuch |
| HGB | Handelsgesetzbuch |
| GmbHG | GmbH-Gesetz |
| GewO | Gewerbeordnung |
| BDSG_2018 | Bundesdatenschutzgesetz |
| DSGVO | Datenschutz-Grundverordnung (EU) |

### Weitere Gesetze — auf Abruf indexierbar

| Bereich | Kürzel (Auswahl) |
|---|---|
| Strafrecht | StGB, StPO, JGG |
| Zivilverfahren | ZPO, GVG |
| Arbeitsrecht | AGG, KSchG, TzBfG, BetrVG, ArbZG, BUrlG, MuSchG |
| Steuerrecht | EStG, UStG |
| Verwaltungsrecht | GG, VwGO, VwVfG |
| Gesellschaftsrecht | AktG, InsO |
| Sozialrecht | SGB I, SGB II, SGB V |
| Sonstige | UrhG, MarkenG, PatG, WpHG, StVG |

```bash
# Alle verfügbaren Gesetze anzeigen
python -m lex_retriever list-available

# Einzelnes Gesetz indexieren
python -m lex_retriever index StGB
```

---

## Embedding-Modelle

Der Embedding-Provider wird in `lex_retriever.toml` konfiguriert. Ein Wechsel erfordert einen Re-Index.

> **Empfehlung:** Mistral für beste Qualität, sentence-transformers für Offline-/Kostenlos-Betrieb.

| Provider | Modell | Qualität | Kosten | API-Key |
|---|---|---|---|---|
| **sentence-transformers** (Standard) | `paraphrase-multilingual-MiniLM-L12-v2` | gut | kostenlos, lokal | nicht nötig |
| **Mistral** ★ Empfohlen | `mistral-embed` | sehr gut | $0.10 / 1M Tokens | `MISTRAL_API_KEY` |
| Google | `text-embedding-004` | gut | kostenloses Kontingent | `GOOGLE_API_KEY` |

### sentence-transformers (Standard, kein API-Key)

Modell (~470 MB) wird beim ersten Start automatisch von HuggingFace heruntergeladen.

```toml
[embedding]
provider = "sentence-transformers"
model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

### Mistral (empfohlen für beste Suchergebnisse)

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

### Google Gemini (kostenloses Kontingent)

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

> API-Key ohne Kreditkarte: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

---

## HTTP API

```bash
pip install -r requirements-api.txt
uvicorn lex_retriever.tool:app --host 0.0.0.0 --port 8000
```

```bash
# Semantische Suche
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Haftung bei Vertragsverletzung", "laws": ["BGB"], "top_k": 5}'

# Einzelner Paragraph
curl "http://localhost:8000/paragraph/BGB/%C2%A7%20280"

# Ganzes Gesetz (paginiert)
curl "http://localhost:8000/law/BGB?offset=0&limit=50"

# Querverweise auflösen
curl -X POST http://localhost:8000/resolve-references \
  -H "Content-Type: application/json" \
  -d '{"text": "Der Schuldner haftet nach § 280 BGB.", "default_law": "BGB"}'
```

Vollständige API-Dokumentation für Agenten: siehe [AGENT.md](AGENT.md).

---

## Konfiguration

### `lex_retriever.toml` (optional)

Platziere `lex_retriever.toml` im Arbeitsverzeichnis. Vorlage: `lex_retriever.toml.example` kopieren.

```toml
[database]
path = "./lancedb"

[laws]
active = ["BGB", "HGB", "GMBHG", "DSGVO", "STGB"]

[embedding]
provider = "sentence-transformers"
model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

### Umgebungsvariablen

| Variable | Standard | Beschreibung |
|---|---|---|
| `LANCE_PATH` | `./lancedb` | Pfad zur LanceDB-Datenbank |
| `LEX_CONFIG` | `lex_retriever.toml` | Pfad zur TOML-Konfigurationsdatei |

---

## CLI-Referenz

```
python -m lex_retriever index-all [--force]        # alle Standard-Gesetze indexieren
python -m lex_retriever index <LAW> [--force]      # einzelnes Gesetz indexieren
python -m lex_retriever list-laws                  # Standard-Gesetze anzeigen
python -m lex_retriever list-available             # alle herunterladbaren Gesetze anzeigen
python -m lex_retriever status                     # lokale DB-Übersicht
```

---

## Für Entwickler: Neuen Provider hinzufügen

1. Erstelle `lex_retriever/providers/my_provider.py`:

```python
from .base import LawProvider

class MyProvider(LawProvider):
    name = "my-source"
    supported_laws = ["STGB"]

    def fetch(self, law_code: str) -> list[dict]:
        # Gibt zurück: [{ "paragraph": str, "text": str, "source": str }]
        ...
```

2. Registriere in `lex_retriever/providers/__init__.py`:

```python
from .my_provider import MyProvider
REGISTRY.append(MyProvider())
```

3. Fertig — `python -m lex_retriever index STGB` und `index-all` nehmen den neuen Provider automatisch auf.

---

## Architektur

```
lex-retriever/
├── lex_retriever/
│   ├── __init__.py          # exportiert search_law()
│   ├── __main__.py          # CLI: python -m lex_retriever
│   ├── retriever.py         # LanceDB-Suchlogik
│   ├── indexer.py           # indiziert Chunks aus Providern
│   ├── tool.py              # Agent-Tool-Wrapper + FastAPI
│   ├── cross_reference.py   # §-Referenz-Extraktion und -Auflösung
│   └── providers/
│       ├── base.py          # LawProvider ABC
│       ├── gesetze_im_internet.py  # deutsche Bundesgesetze (XML-ZIP)
│       └── eur_lex.py       # EU-Verordnungen (DSGVO)
├── lancedb/                 # lokale Vektordatenbank (git-ignored)
├── tests/
├── requirements.txt
├── requirements-api.txt
└── lex_retriever.toml.example
```

---

## Tests

```bash
pip install pytest

pytest tests/ -v                         # alle Tests
pytest -m "not requires_db" -v          # nur Unit-Tests (ohne DB)
pytest -m "requires_db" -v              # DB-abhängige Tests (Index nötig)
```

---

## Lizenz

MIT — siehe LICENSE.
