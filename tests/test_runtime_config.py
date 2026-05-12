from __future__ import annotations

from pathlib import Path

import pytest

from lex_retriever.runtime_config import resolve_config_path


def test_resolve_config_path_prefers_cwd_file(monkeypatch, tmp_path):
    monkeypatch.delenv("LEX_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "lex_retriever.toml").write_bytes(b"")

    path = resolve_config_path()
    assert path == (tmp_path / "lex_retriever.toml").resolve()


def test_resolve_config_path_falls_back_to_pkg_root(monkeypatch, tmp_path):
    """When no CWD config exists, fall back to the package-root path."""
    monkeypatch.delenv("LEX_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    # No lex_retriever.toml in tmp_path

    path = resolve_config_path()

    import lex_retriever.runtime_config as _rc
    expected = (Path(_rc.__file__).parent.parent / "lex_retriever.toml").resolve()
    assert path == expected


def test_resolve_config_path_env_raises_if_not_found(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LEX_CONFIG", "configs/custom.toml")

    with pytest.raises(FileNotFoundError, match="LEX_CONFIG="):
        resolve_config_path()


def test_resolve_config_path_env_returns_path_when_found(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_file = config_dir / "custom.toml"
    config_file.write_bytes(b"")
    monkeypatch.setenv("LEX_CONFIG", "configs/custom.toml")

    path = resolve_config_path()
    assert path == config_file.resolve()


def test_resolve_config_path_expands_home(monkeypatch, tmp_path):
    config_file = tmp_path / "lex_retriever.toml"
    config_file.write_bytes(b"")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LEX_CONFIG", "~/lex_retriever.toml")

    path = resolve_config_path()
    assert str(path).startswith(str(tmp_path))
