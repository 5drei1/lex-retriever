"""Runtime config helpers for CLI/tool entrypoints."""

from __future__ import annotations

import os
from pathlib import Path

_CONFIG_FILENAME = "lex_retriever.toml"


def resolve_config_path() -> Path:
    """Return the best available config path.

    Priority:
    1. LEX_CONFIG env var — raises FileNotFoundError if the path doesn't exist.
    2. lex_retriever.toml in the current working directory.
    3. lex_retriever.toml next to the package root (installed alongside the package).

    Callers should still check .exists() for cases 2/3 in case no config is present.
    """
    env_var = os.environ.get("LEX_CONFIG")
    if env_var:
        path = Path(env_var).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if not path.exists():
            raise FileNotFoundError(
                f"LEX_CONFIG={env_var!r} resolved to {path} but file was not found"
            )
        return path

    cwd_path = (Path.cwd() / _CONFIG_FILENAME).resolve()
    if cwd_path.exists():
        return cwd_path

    return (Path(__file__).parent.parent / _CONFIG_FILENAME).resolve()
