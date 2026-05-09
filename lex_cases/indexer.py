"""Indexer: embed and store German court decisions in LanceDB."""

from __future__ import annotations

import hashlib
import logging
import os

import lancedb

from lex_retriever.embeddings import get_embedding_provider

logger = logging.getLogger(__name__)

LANCE_PATH = os.environ.get("CASE_LANCE_PATH", os.path.join(os.path.dirname(__file__), "..", "lancedb"))
TABLE_NAME = "german_cases"
_ALL_COURTS = ["BGH", "BVERFG", "BAG", "BFH", "BVERWG", "BPATG"]
_BATCH_SIZE = 16  # Mistral API limit per request


def make_case_id(court: str, az: str, chunk_idx: int) -> str:
    return hashlib.sha1(f"{court}|{az}|{chunk_idx}".encode()).hexdigest()


def _open_table(db: lancedb.DBConnection):
    if TABLE_NAME in db.table_names():
        return db.open_table(TABLE_NAME)
    return None


def _get_existing_ids(table) -> set[str]:
    try:
        rows = table.search().select(["id"]).to_list()
        return {r["id"] for r in rows}
    except Exception:
        return set()


def index_cases(
    cases: list[dict],
    embedding_config: dict | None = None,
    db_path: str = LANCE_PATH,
) -> int:
    """Embed case chunks and store in LanceDB german_cases table.

    Each case dict must have: court, az, date, type, text, chunk_type, laws_cited, url.
    Already-indexed IDs (SHA1 of court|az|chunk_idx) are skipped.
    Returns the number of rows newly indexed.
    """
    if not cases:
        return 0

    embedder = get_embedding_provider(embedding_config)
    os.makedirs(db_path, exist_ok=True)
    db = lancedb.connect(db_path)
    table = _open_table(db)
    existing_ids = _get_existing_ids(table) if table is not None else set()

    rows_to_add: list[dict] = []
    for idx, case in enumerate(cases):
        case_id = make_case_id(case.get("court", ""), case.get("az", ""), idx)
        if case_id in existing_ids:
            continue
        rows_to_add.append({
            "id":         case_id,
            "court":      case.get("court", ""),
            "az":         case.get("az", ""),
            "date":       case.get("date", ""),
            "type":       case.get("type", ""),
            "chunk_type": case.get("chunk_type", ""),
            "text":       case.get("text", ""),
            "laws_cited": case.get("laws_cited") or [],
            "url":        case.get("url", ""),
        })

    if not rows_to_add:
        return 0

    texts = [r["text"] for r in rows_to_add]
    all_vectors: list[list[float]] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start:start + _BATCH_SIZE]
        all_vectors.extend(embedder.embed(batch))

    rows = [{**row, "vector": vec} for row, vec in zip(rows_to_add, all_vectors)]

    if table is None:
        table = db.create_table(TABLE_NAME, data=rows[:_BATCH_SIZE])
        for start in range(_BATCH_SIZE, len(rows), _BATCH_SIZE):
            table.add(rows[start:start + _BATCH_SIZE])
    else:
        for start in range(0, len(rows), _BATCH_SIZE):
            table.add(rows[start:start + _BATCH_SIZE])

    return len(rows)


def index_court(court: str, db_path: str = LANCE_PATH, embedding_config: dict | None = None) -> int:
    """Fetch and index all decisions for a single court."""
    from .providers.rechtsprechung_im_internet import fetch_court_xml_zip
    cases = fetch_court_xml_zip(court)
    return index_cases(cases, embedding_config=embedding_config, db_path=db_path)


def index_all_courts(db_path: str = LANCE_PATH, embedding_config: dict | None = None) -> dict[str, int]:
    """Index all 6 German federal courts."""
    return {court: index_court(court, db_path=db_path, embedding_config=embedding_config)
            for court in _ALL_COURTS}


def get_court_counts(db_path: str = LANCE_PATH) -> dict[str, int]:
    """Return row count per court from LanceDB."""
    try:
        db = lancedb.connect(db_path)
        if TABLE_NAME not in db.table_names():
            return {}
        rows = db.open_table(TABLE_NAME).search().select(["court"]).to_list()
        counts: dict[str, int] = {}
        for r in rows:
            c = r.get("court", "unknown")
            counts[c] = counts.get(c, 0) + 1
        return counts
    except Exception:
        return {}
