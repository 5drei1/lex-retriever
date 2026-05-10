"""CLI entrypoint: python -m lex_retriever"""
import os
import sys
import tomllib
from pathlib import Path


def _load_config() -> dict:
    config_path = Path(os.environ.get("LEX_CONFIG", "lex_retriever.toml"))
    if config_path.exists():
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    return {}


def main():
    """Entry point for the lex-retriever CLI (python -m lex_retriever <command>)."""
    config = _load_config()
    active_laws: list[str] | None = config.get("laws", {}).get("active")
    db_path: str | None = config.get("database", {}).get("path")
    embedding_config: dict = config.get("embedding", {}) or {}

    if db_path:
        os.environ.setdefault("CHROMA_PATH", db_path)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "index-all":
        from .indexer import index_all_laws
        force = "--force" in sys.argv
        law_codes = [l.upper() for l in active_laws] if active_laws else None
        if law_codes:
            print(f"Using active laws from config: {', '.join(law_codes)}")
        if embedding_config:
            print(f"Embedding provider: {embedding_config.get('provider', 'sentence-transformers')}")
        results = index_all_laws(force=force, law_codes=law_codes, embedding_config=embedding_config)
        for law, count in results.items():
            status = f"{count} chunks indexed" if count > 0 else "already up to date"
            print(f"  {law}: {status}")

    elif cmd == "index" and len(sys.argv) > 2:
        from .indexer import index_law
        law_code = sys.argv[2].upper()
        force = "--force" in sys.argv
        count = index_law(law_code, force=force, embedding_config=embedding_config)
        status = f"{count} chunks indexed" if count > 0 else "already up to date (use --force to re-index)"
        print(f"{law_code}: {status}")

    elif cmd == "list-laws":
        from .providers import all_supported_laws
        laws = all_supported_laws()
        print("Default laws across all providers:")
        for law in laws:
            print(f"  - {law}")

    elif cmd == "list-available":
        from .providers import REGISTRY
        from .indexer import get_indexed_law_counts

        try:
            indexed_counts = get_indexed_law_counts()
        except Exception:
            indexed_counts = {}

        for provider in REGISTRY:
            laws = provider.available_laws()
            print(f"\n[{provider.name}]")
            for law in laws:
                code = law["code"]
                name = law["full_name"]
                is_indexed = code.upper() in indexed_counts
                mark = "✓ indexed    " if is_indexed else "✗ not indexed"
                print(f"  {code:<14} {name[:50]:<50}  {mark}")

        print("\nRun: python -m lex_retriever index <LAW_CODE> to add a law to your DB.")

    elif cmd == "status":
        from .providers import REGISTRY
        from .indexer import get_indexed_law_counts, LANCE_PATH

        indexed = get_indexed_law_counts()

        all_available: set[str] = set()
        for provider in REGISTRY:
            for law in provider.available_laws():
                all_available.add(law["code"].upper())

        print(f"Local DB: {LANCE_PATH}")
        if not indexed:
            print("Indexed laws: 0  (run `python -m lex_retriever index-all` to populate)")
        else:
            print(f"Indexed laws: {len(indexed)}")
            for law, count in sorted(indexed.items()):
                print(f"  ✓ {law:<14} ({count:,} chunks)")

        not_indexed_count = len(all_available - set(indexed.keys()))
        print(f"\nAvailable but not indexed: {not_indexed_count} laws")

        if active_laws:
            missing = [l for l in active_laws if l.upper() not in indexed]
            if missing:
                print(f"  ⚠ Missing from your active config: {', '.join(missing)}")
                print("  Run `python -m lex_retriever index-all` to index them.")

        print("Run `python -m lex_retriever list-available` to see all available laws.")

    else:
        print("Usage:")
        print("  python -m lex_retriever index-all [--force]          # index active/default laws")
        print("  python -m lex_retriever index <LAW_CODE> [--force]   # index a specific law")
        print("  python -m lex_retriever list-laws                    # list default configured laws")
        print("  python -m lex_retriever list-available               # list ALL downloadable laws")
        print("  python -m lex_retriever status                       # show local DB state")
        print()
        print("Config: place lex_retriever.toml in the working directory (see lex_retriever.toml.example)")
        print("        or set LEX_CONFIG=/path/to/config.toml")


if __name__ == "__main__":
    main()
