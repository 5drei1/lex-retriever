"""Config loading and validation for lex-retriever provider sections."""
from __future__ import annotations

import os
from typing import Any


class ConfigError(ValueError):
    """Raised when config is invalid or a required environment variable is missing."""


def _resolve_api_key(section_name: str, section: dict[str, Any]) -> str | None:
    """Return the API key from the env var named by api_key_env.

    Raises ConfigError if api_key_env is set but the env var is absent/empty.
    Returns None when api_key_env is not configured (key not required).
    """
    api_key_env = section.get("api_key_env")
    if not api_key_env:
        return None
    value = os.environ.get(str(api_key_env))
    if not value:
        raise ConfigError(
            f"[{section_name}] api_key_env = \"{api_key_env}\" is configured, "
            f"but the environment variable '{api_key_env}' is not set. "
            f"Fix: export {api_key_env}=<your-key>"
        )
    return value


def validate_neuris_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate the [neuris] section and resolve the API key.

    Returns a copy of the section dict with '_api_key' added.
    Raises ConfigError on invalid transport or missing required env var.
    """
    section = dict(config.get("neuris") or {})
    transport = section.get("transport", "testphase")
    valid = ("testphase", "production")
    if transport not in valid:
        raise ConfigError(
            f"[neuris] transport must be one of {valid}, got: {transport!r}"
        )
    section["transport"] = transport
    section["_api_key"] = _resolve_api_key("neuris", section)
    return section


def validate_cellar_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate the [cellar] section and resolve the API key.

    Returns a copy of the section dict with '_api_key' added.
    Raises ConfigError on missing required env var.
    """
    section = dict(config.get("cellar") or {})
    section["_api_key"] = _resolve_api_key("cellar", section)
    return section


def validate_provider_configs(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Validate all provider sections in the loaded config.

    Returns {'neuris': <resolved>, 'cellar': <resolved>}.
    Raises ConfigError on the first validation failure encountered.
    """
    return {
        "neuris": validate_neuris_config(config),
        "cellar": validate_cellar_config(config),
    }
