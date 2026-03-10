"""Tests for the unified LLM client (src/llm_client.py)."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.llm_client import call_llm, is_ollama_model, get_ollama_model_name, _call_ollama


class TestModelDetection:
    def test_is_ollama_model_true(self):
        assert is_ollama_model("ollama:qwen3.5") is True
        assert is_ollama_model("ollama:devstral") is True
        assert is_ollama_model("ollama:gemma3") is True

    def test_is_ollama_model_false(self):
        assert is_ollama_model("claude") is False
        assert is_ollama_model("claude-sonnet-4-5-20250929") is False

    def test_get_ollama_model_name(self):
        assert get_ollama_model_name("ollama:qwen3.5") == "qwen3.5"
        assert get_ollama_model_name("ollama:devstral") == "devstral"
        assert get_ollama_model_name("ollama:gemma3") == "gemma3"


class TestCallLlmClaude:
    """Test that call_llm routes to Claude API for non-ollama models."""

    @patch("src.api.call_api")
    def test_routes_to_claude(self, mock_api):
        mock_api.return_value = "Claude response"

        result = call_llm(
            system="You are helpful.",
            user_content="Hello",
            model="claude",
            max_tokens=100,
        )

        assert result == "Claude response"
        mock_api.assert_called_once_with(
            model="claude-sonnet-4-5-20250929",
            max_tokens=100,
            system="You are helpful.",
            user_content="Hello",
        )

    @patch("src.api.call_api")
    def test_default_model_is_claude(self, mock_api):
        mock_api.return_value = "ok"

        call_llm(system="sys", user_content="hi")

        call_kwargs = mock_api.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"

    @patch("src.api.call_api")
    def test_passes_custom_claude_model(self, mock_api):
        mock_api.return_value = "ok"

        call_llm(system="sys", user_content="hi", model="claude-opus-4-5-20250918")

        call_kwargs = mock_api.call_args.kwargs
        assert call_kwargs["model"] == "claude-opus-4-5-20250918"


class TestCallLlmOllama:
    """Test that call_llm routes to Ollama for ollama: prefixed models."""

    @patch("src.llm_client.httpx.post")
    def test_routes_to_ollama(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Ollama response text"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = call_llm(
            system="You are helpful.",
            user_content="Hello",
            model="ollama:qwen3.5",
        )

        assert result == "Ollama response text"
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args.kwargs["json"]["model"] == "qwen3.5"
        assert call_args.kwargs["json"]["stream"] is False

    @patch("src.llm_client.httpx.post")
    def test_ollama_sends_system_and_user_messages(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": "ok"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        call_llm(
            system="Be concise.",
            user_content="Say hi",
            model="ollama:devstral",
        )

        payload = mock_post.call_args.kwargs["json"]
        assert payload["messages"] == [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Say hi"},
        ]

    @patch("src.llm_client.httpx.post")
    def test_ollama_connection_error(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(ConnectionError, match="Could not connect to Ollama"):
            call_llm(
                system="sys",
                user_content="hi",
                model="ollama:qwen3.5",
            )

    @patch("src.llm_client.httpx.post")
    def test_ollama_http_error(self, mock_post):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "model not found"
        mock_post.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_response
        )

        with pytest.raises(RuntimeError, match="Ollama API error"):
            call_llm(
                system="sys",
                user_content="hi",
                model="ollama:nonexistent",
            )

    @patch("src.llm_client.httpx.post")
    def test_ollama_empty_response(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": ""}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with pytest.raises(RuntimeError, match="Empty response"):
            call_llm(
                system="sys",
                user_content="hi",
                model="ollama:qwen3.5",
            )

    @patch("src.llm_client.httpx.post")
    def test_ollama_uses_custom_base_url(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ok"}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        _call_ollama(
            model_name="gemma3",
            system="sys",
            user_content="hi",
            base_url="http://ollama:11434",
        )

        url = mock_post.call_args.args[0]
        assert url == "http://ollama:11434/api/chat"

    @patch("src.llm_client.httpx.post")
    def test_ollama_uses_correct_url(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ok"}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        call_llm(
            system="sys",
            user_content="hi",
            model="ollama:gemma3",
        )

        url = mock_post.call_args.args[0]
        assert url == "http://localhost:11434/api/chat"
