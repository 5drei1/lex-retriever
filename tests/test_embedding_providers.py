"""Tests for pluggable embedding providers (Mistral and Google, mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestGetEmbeddingProvider:
    def test_default_returns_sentence_transformers(self):
        from lex_retriever.embeddings import get_embedding_provider
        from lex_retriever.embeddings.sentence_transformers import SentenceTransformersProvider

        with patch("sentence_transformers.SentenceTransformer"):
            provider = get_embedding_provider({})
        assert isinstance(provider, SentenceTransformersProvider)

    def test_unknown_provider_raises(self):
        from lex_retriever.embeddings import get_embedding_provider

        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_embedding_provider({"provider": "nonexistent"})


class TestMistralEmbeddingProvider:
    def _make_provider(self, model="mistral-embed", api_key="test-key"):
        mock_mistral_cls = MagicMock()
        mock_client = MagicMock()
        mock_mistral_cls.return_value = mock_client

        with patch.dict("sys.modules", {"mistralai": MagicMock(Mistral=mock_mistral_cls)}):
            from lex_retriever.embeddings.mistral import MistralEmbeddingProvider

            provider = MistralEmbeddingProvider(model=model, api_key=api_key)

        provider.client = mock_client
        return provider, mock_client

    def test_name_and_dimensions(self):
        from lex_retriever.embeddings.mistral import MistralEmbeddingProvider

        mock_cls = MagicMock()
        with patch.dict("sys.modules", {"mistralai": MagicMock(Mistral=mock_cls)}):
            provider = MistralEmbeddingProvider.__new__(MistralEmbeddingProvider)
            provider.model = "mistral-embed"
            provider.client = MagicMock()

        assert MistralEmbeddingProvider.name == "mistral"
        assert MistralEmbeddingProvider.dimensions == 1024

    def test_embed_calls_api_and_returns_vectors(self):
        provider, mock_client = self._make_provider()

        fake_vec = [0.1, 0.2, 0.3]
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=fake_vec)]
        mock_client.embeddings.create.return_value = mock_response

        result = provider.embed(["Test sentence"])

        mock_client.embeddings.create.assert_called_once_with(
            model="mistral-embed", inputs=["Test sentence"]
        )
        assert result == [fake_vec]

    def test_embed_multiple_texts(self):
        provider, mock_client = self._make_provider()

        vecs = [[0.1, 0.2], [0.3, 0.4]]
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=v) for v in vecs]
        mock_client.embeddings.create.return_value = mock_response

        result = provider.embed(["First", "Second"])
        assert result == vecs

    def test_factory_creates_mistral_provider(self):
        from lex_retriever.embeddings import get_embedding_provider
        from lex_retriever.embeddings.mistral import MistralEmbeddingProvider

        mock_cls = MagicMock()
        mock_cls.return_value = MagicMock()
        with patch.dict("sys.modules", {"mistralai": MagicMock(Mistral=mock_cls)}):
            provider = get_embedding_provider(
                {"provider": "mistral", "model": "mistral-embed", "api_key_env": "MISTRAL_API_KEY"}
            )

        assert isinstance(provider, MistralEmbeddingProvider)


class TestGoogleEmbeddingProvider:
    def _make_provider(self, model="text-embedding-004", api_key="test-key"):
        mock_genai = MagicMock()

        with patch.dict("sys.modules", {"google.generativeai": mock_genai, "google": MagicMock()}):
            from lex_retriever.embeddings.google import GoogleEmbeddingProvider

            provider = GoogleEmbeddingProvider(model=model, api_key=api_key)

        provider._genai = mock_genai
        return provider, mock_genai

    def test_name_and_dimensions(self):
        assert __import__(
            "lex_retriever.embeddings.google", fromlist=["GoogleEmbeddingProvider"]
        )

        from lex_retriever.embeddings.google import GoogleEmbeddingProvider

        mock_genai = MagicMock()
        with patch.dict("sys.modules", {"google.generativeai": mock_genai, "google": MagicMock()}):
            provider = GoogleEmbeddingProvider.__new__(GoogleEmbeddingProvider)
            provider.model = "text-embedding-004"
            provider._genai = mock_genai

        assert GoogleEmbeddingProvider.name == "google"
        assert GoogleEmbeddingProvider.dimensions == 768

    def test_embed_calls_api_and_returns_vectors(self):
        provider, mock_genai = self._make_provider()

        fake_vec = [0.5, 0.6, 0.7]
        mock_genai.embed_content.return_value = {"embedding": fake_vec}

        result = provider.embed(["Ein Testtext"])

        mock_genai.embed_content.assert_called_once_with(
            model="models/text-embedding-004",
            content="Ein Testtext",
            task_type="retrieval_document",
        )
        assert result == [fake_vec]

    def test_embed_multiple_texts(self):
        provider, mock_genai = self._make_provider()

        vecs = [[0.1, 0.2], [0.3, 0.4]]
        mock_genai.embed_content.side_effect = [{"embedding": v} for v in vecs]

        result = provider.embed(["First", "Second"])
        assert result == vecs

    def test_factory_creates_google_provider(self):
        from lex_retriever.embeddings import get_embedding_provider
        from lex_retriever.embeddings.google import GoogleEmbeddingProvider

        mock_genai = MagicMock()
        with patch.dict("sys.modules", {"google.generativeai": mock_genai, "google": MagicMock()}):
            provider = get_embedding_provider(
                {"provider": "google", "model": "text-embedding-004", "api_key_env": "GOOGLE_API_KEY"}
            )

        assert isinstance(provider, GoogleEmbeddingProvider)


