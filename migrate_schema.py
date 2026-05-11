#!/usr/bin/env python3
"""Schema migration: drop old german_law table and re-index with ref_id schema.

The AIG-137 schema change removes the text column from the german_law LanceDB
table. Existing tables must be deleted and re-created because LanceDB does not
support column removal migrations.

Usage:
    python migrate_schema.py [--laws BGB HGB ...] [--force]

Without --laws all laws known to the active providers are re-indexed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

LANCE_PATH = os.environ.get("LANCE_PATH", os.path.join(os.path.dirname(__file__), "lancedb"))
TABLE_DIR = os.path.join(LANCE_PATH, "german_law.lance")


def drop_old_table() -> None:
    if os.path.exists(TABLE_DIR):
        print(f"Dropping old table: {TABLE_DIR}")
        shutil.rmtree(TABLE_DIR)
    else:
        print("No existing table found — nothing to drop.")


def reindex(law_codes: list[str] | None, force: bool) -> None:
    from lex_retriever.indexer import index_law, index_all_laws

    if law_codes:
        results = {}
        for code in law_codes:
            print(f"  Indexing {code}…", end=" ", flush=True)
            try:
                n = index_law(code, force=force)
                results[code] = n
                print(f"{n} chunks")
            except Exception as exc:
                print(f"ERROR: {exc}")
                results[code] = -1
    else:
        print("Indexing all supported laws…")
        results = index_all_laws(force=force)
        for code, n in results.items():
            print(f"  {code}: {n} chunks")

    total = sum(n for n in results.values() if n >= 0)
    print(f"\nDone. Total chunks indexed: {total}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--laws", nargs="+", metavar="CODE",
                        help="Law codes to re-index (default: all)")
    parser.add_argument("--force", action="store_true",
                        help="Force re-index even if already indexed")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only show what would be done, without executing")
    args = parser.parse_args()

    if args.dry_run:
        print("[dry-run] Would drop:", TABLE_DIR)
        if args.laws:
            print("[dry-run] Would re-index:", " ".join(args.laws))
        else:
            print("[dry-run] Would re-index all supported laws")
        return

    drop_old_table()
    reindex(args.laws, args.force)


if __name__ == "__main__":
    main()
