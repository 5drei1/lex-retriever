"""CLI entrypoint: python -m lex_cases"""

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m lex_cases",
        description="lex-cases: semantic search over German federal court decisions",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # index <COURT>
    p_index = sub.add_parser("index", help="Index decisions for a single court")
    p_index.add_argument("court", metavar="COURT",
                         help="Court code: BGH, BVERFG, BAG, BFH, BVERWG, BPATG")

    # index-all
    sub.add_parser("index-all", help="Index all 6 German federal courts")

    # status
    sub.add_parser("status", help="Show per-court row counts in the index")

    # search <query>
    p_search = sub.add_parser("search", help="Semantic search over indexed decisions")
    p_search.add_argument("query", metavar="QUERY", help="Search query")
    p_search.add_argument("-c", "--court", dest="courts", action="append",
                          metavar="COURT", default=None,
                          help="Filter by court code (repeatable)")
    p_search.add_argument("-l", "--laws", dest="laws_cited", action="append",
                          metavar="LAW", default=None,
                          help="Filter by laws_cited substring (repeatable)")
    p_search.add_argument("-k", "--top-k", dest="top_k", type=int, default=10,
                          metavar="N", help="Number of results (default: 10)")

    return parser


def _cmd_index(args) -> None:
    from .indexer import index_court
    court = args.court.upper()
    print(f"Indexing {court}...")
    n = index_court(court)
    if n == 0:
        print(f"  {court}: already up to date (skipped)")
    else:
        print(f"  {court}: {n} chunks indexed")


def _cmd_index_all() -> None:
    from .indexer import index_all_courts, _ALL_COURTS
    print(f"Indexing all {len(_ALL_COURTS)} courts...")
    results = index_all_courts()
    for court, n in results.items():
        status = f"{n} chunks indexed" if n > 0 else "already up to date"
        print(f"  {court}: {status}")


def _cmd_status() -> None:
    from .indexer import get_court_counts, _ALL_COURTS, LANCE_PATH
    from .providers.rechtsprechung_im_internet import _COURT_CATALOG
    counts = get_court_counts()
    if not counts:
        print(f"Index is empty. Run: python -m lex_cases index-all")
        print(f"  DB path: {LANCE_PATH}")
        return

    # Build lookup: short code → full name and reverse
    code_to_full = {code: full for code, (full, _) in _COURT_CATALOG.items()}
    full_to_code = {full: code for code, full in code_to_full.items()}

    total = sum(counts.values())
    print(f"Index: {LANCE_PATH}")
    print(f"{'Court':<14} {'Rows':>8}")
    print("-" * 24)
    for court in _ALL_COURTS:
        full_name = code_to_full.get(court, court)
        # Count may be keyed by full name or short code
        n = counts.get(court, 0) + counts.get(full_name, 0)
        mark = f"{n:>8}" if n > 0 else "  (empty)"
        print(f"  {court:<12} {mark}")
    # Show any court names in DB not matched by the catalog
    known = set(code_to_full.keys()) | set(code_to_full.values())
    extra = {k: v for k, v in counts.items() if k not in known}
    for name, n in sorted(extra.items()):
        code = full_to_code.get(name, name)
        print(f"  {code:<12} {n:>8}")
    print("-" * 24)
    print(f"  {'Total':<12} {total:>8}")


def _cmd_search(args) -> None:
    from .retriever import LexCaseRetriever
    retriever = LexCaseRetriever()
    try:
        results = retriever.search(
            args.query,
            courts=args.courts,
            laws_cited=args.laws_cited,
            top_k=args.top_k,
        )
    except Exception as exc:
        print(f"Search failed: {exc}", file=sys.stderr)
        print("Tip: run `python -m lex_cases index-all` to populate the index first.",
              file=sys.stderr)
        sys.exit(1)

    if not results:
        print("No results found.")
        return

    for i, r in enumerate(results, 1):
        laws = ", ".join(r.get("laws_cited") or []) or "-"
        print(f"\n[{i}] {r.get('court','')} — {r.get('az','')} ({r.get('date','')})")
        print(f"    Type : {r.get('type','')}")
        print(f"    Laws : {laws}")
        print(f"    Score: {r.get('score', 0):.3f}")
        print(f"    URL  : {r.get('url','')}")
        text = (r.get("text") or r.get("leitsatz") or "").strip()
        if text:
            preview = text[:300] + ("…" if len(text) > 300 else "")
            print(f"    Text : {preview}")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "index":
        _cmd_index(args)
    elif args.command == "index-all":
        _cmd_index_all()
    elif args.command == "status":
        _cmd_status()
    elif args.command == "search":
        _cmd_search(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
