"""CLI entrypoint: python -m lex_retriever"""
import sys


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "index-all":
        from .indexer import index_all_laws
        force = "--force" in sys.argv
        results = index_all_laws(force=force)
        for law, count in results.items():
            status = f"{count} chunks indexed" if count > 0 else "already up to date"
            print(f"  {law}: {status}")

    elif cmd == "index" and len(sys.argv) > 2:
        from .indexer import index_law
        law_code = sys.argv[2].upper()
        force = "--force" in sys.argv
        count = index_law(law_code, force=force)
        status = f"{count} chunks indexed" if count > 0 else "already up to date (use --force to re-index)"
        print(f"{law_code}: {status}")

    elif cmd == "list-laws":
        from .providers import all_supported_laws
        laws = all_supported_laws()
        print("Available laws across all providers:")
        for law in laws:
            print(f"  - {law}")

    else:
        print("Usage:")
        print("  python -m lex_retriever index-all [--force]")
        print("  python -m lex_retriever index <LAW_CODE> [--force]")
        print("  python -m lex_retriever list-laws")


if __name__ == "__main__":
    main()
