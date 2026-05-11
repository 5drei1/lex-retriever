"""Tests for lex_retriever.config — [neuris] and [cellar] section validation."""
import os
import pytest

from lex_retriever.config import (
    ConfigError,
    validate_neuris_config,
    validate_cellar_config,
    validate_provider_configs,
)


class TestValidateNeurisConfig:
    def test_empty_config_uses_testphase_default(self):
        result = validate_neuris_config({})
        assert result["transport"] == "testphase"
        assert result["_api_key"] is None

    def test_explicit_testphase_transport(self):
        result = validate_neuris_config({"neuris": {"transport": "testphase"}})
        assert result["transport"] == "testphase"

    def test_production_transport_accepted(self):
        result = validate_neuris_config({"neuris": {"transport": "production"}})
        assert result["transport"] == "production"

    def test_invalid_transport_raises_config_error(self):
        with pytest.raises(ConfigError, match="transport must be one of"):
            validate_neuris_config({"neuris": {"transport": "invalid"}})

    def test_api_key_env_resolved_when_set(self, monkeypatch):
        monkeypatch.setenv("NEURIS_API_KEY", "secret-token")
        result = validate_neuris_config({"neuris": {"api_key_env": "NEURIS_API_KEY"}})
        assert result["_api_key"] == "secret-token"

    def test_api_key_env_missing_raises_config_error(self, monkeypatch):
        monkeypatch.delenv("NEURIS_API_KEY", raising=False)
        with pytest.raises(ConfigError, match="NEURIS_API_KEY"):
            validate_neuris_config({"neuris": {"api_key_env": "NEURIS_API_KEY"}})

    def test_error_message_includes_export_hint(self, monkeypatch):
        monkeypatch.delenv("NEURIS_API_KEY", raising=False)
        with pytest.raises(ConfigError, match="export NEURIS_API_KEY"):
            validate_neuris_config({"neuris": {"api_key_env": "NEURIS_API_KEY"}})

    def test_no_api_key_env_returns_none(self):
        result = validate_neuris_config({"neuris": {"transport": "testphase"}})
        assert result["_api_key"] is None


class TestValidateCellarConfig:
    def test_empty_config_succeeds(self):
        result = validate_cellar_config({})
        assert result["_api_key"] is None

    def test_endpoint_preserved(self):
        ep = "https://publications.europa.eu/webapi/rdf/sparql"
        result = validate_cellar_config({"cellar": {"endpoint": ep}})
        assert result["endpoint"] == ep

    def test_api_key_env_resolved_when_set(self, monkeypatch):
        monkeypatch.setenv("CELLAR_API_KEY", "cellar-secret")
        result = validate_cellar_config({"cellar": {"api_key_env": "CELLAR_API_KEY"}})
        assert result["_api_key"] == "cellar-secret"

    def test_api_key_env_missing_raises_config_error(self, monkeypatch):
        monkeypatch.delenv("CELLAR_API_KEY", raising=False)
        with pytest.raises(ConfigError, match="CELLAR_API_KEY"):
            validate_cellar_config({"cellar": {"api_key_env": "CELLAR_API_KEY"}})

    def test_error_message_includes_export_hint(self, monkeypatch):
        monkeypatch.delenv("CELLAR_API_KEY", raising=False)
        with pytest.raises(ConfigError, match="export CELLAR_API_KEY"):
            validate_cellar_config({"cellar": {"api_key_env": "CELLAR_API_KEY"}})


class TestValidateProviderConfigs:
    def test_empty_config_succeeds(self):
        result = validate_provider_configs({})
        assert "neuris" in result
        assert "cellar" in result
        assert result["neuris"]["_api_key"] is None
        assert result["cellar"]["_api_key"] is None

    def test_full_valid_config(self, monkeypatch):
        monkeypatch.setenv("NEURIS_API_KEY", "n-key")
        monkeypatch.setenv("CELLAR_API_KEY", "c-key")
        config = {
            "neuris": {"transport": "production", "api_key_env": "NEURIS_API_KEY"},
            "cellar": {"api_key_env": "CELLAR_API_KEY"},
        }
        result = validate_provider_configs(config)
        assert result["neuris"]["_api_key"] == "n-key"
        assert result["cellar"]["_api_key"] == "c-key"

    def test_neuris_error_surfaces_immediately(self, monkeypatch):
        monkeypatch.delenv("NEURIS_API_KEY", raising=False)
        config = {"neuris": {"api_key_env": "NEURIS_API_KEY"}}
        with pytest.raises(ConfigError, match="NEURIS_API_KEY"):
            validate_provider_configs(config)
