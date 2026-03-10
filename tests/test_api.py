"""Tests for the shared API call helpers (src/api.py)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.api import call_api, parse_json_response


class TestCallApi:
    """Tests for the call_api function with mocked Claude client."""

    @patch("src.api.anthropic.Anthropic")
    def test_returns_text_content(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_block = MagicMock()
        mock_block.text = "Hello from Claude"
        mock_message = MagicMock()
        mock_message.content = [mock_block]
        mock_client.messages.create.return_value = mock_message

        result = call_api(
            model="claude-sonnet-4-5-20250929",
            max_tokens=100,
            system="You are a helpful assistant.",
            user_content="Say hello",
        )

        assert result == "Hello from Claude"
        mock_client.messages.create.assert_called_once()

    @patch("src.api.anthropic.Anthropic")
    def test_passes_correct_params(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_block = MagicMock()
        mock_block.text = "ok"
        mock_message = MagicMock()
        mock_message.content = [mock_block]
        mock_client.messages.create.return_value = mock_message

        call_api(
            model="test-model",
            max_tokens=256,
            system="system prompt",
            user_content="user prompt",
        )

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "test-model"
        assert call_kwargs.kwargs["max_tokens"] == 256
        assert call_kwargs.kwargs["system"] == "system prompt"
        assert call_kwargs.kwargs["messages"] == [
            {"role": "user", "content": "user prompt"}
        ]

    @patch("src.api.anthropic.Anthropic")
    def test_propagates_non_retryable_error(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = ValueError("bad input")

        with pytest.raises(ValueError, match="bad input"):
            call_api(
                model="test-model",
                max_tokens=100,
                system="sys",
                user_content="user",
            )


class TestParseJsonResponse:
    """Tests for the parse_json_response utility."""

    def test_plain_json(self):
        result = parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_code_block(self):
        text = '```json\n{"key": "value"}\n```'
        result = parse_json_response(text)
        assert result == {"key": "value"}

    def test_bare_code_block(self):
        text = '```\n{"key": "value"}\n```'
        result = parse_json_response(text)
        assert result == {"key": "value"}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result:\n```json\n{"score": 85}\n```\nDone.'
        result = parse_json_response(text)
        assert result == {"score": 85}

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_json_response("not json at all")

    def test_nested_json(self):
        data = {"outer": {"inner": [1, 2, 3]}}
        result = parse_json_response(json.dumps(data))
        assert result == data

    def test_json_embedded_in_prose(self):
        text = 'Here is the analysis:\n{"score": 85, "match": true}\nHope that helps!'
        result = parse_json_response(text)
        assert result == {"score": 85, "match": True}

    def test_trailing_commas(self):
        text = '{"key": "value", "list": [1, 2, 3,],}'
        result = parse_json_response(text)
        assert result == {"key": "value", "list": [1, 2, 3]}

    def test_single_quotes_only(self):
        text = "{'key': 'value', 'num': 42}"
        result = parse_json_response(text)
        assert result == {"key": "value", "num": 42}

    def test_json_array_in_prose(self):
        text = 'The results are: [{"a": 1}, {"b": 2}] end.'
        result = parse_json_response(text)
        assert result == [{"a": 1}, {"b": 2}]

    def test_extra_data_after_json(self):
        """Ollama sometimes returns valid JSON followed by extra text."""
        text = '{"score": 85, "match": true}\n\nHere is some extra explanation text.'
        result = parse_json_response(text)
        assert result == {"score": 85, "match": True}

    def test_extra_data_in_code_fence(self):
        text = '```json\n{"key": "value"}\n```\nextra stuff\n{"another": "object"}'
        result = parse_json_response(text)
        assert result == {"key": "value"}

    def test_extra_data_complex_object(self):
        """Valid JSON object followed by another JSON object."""
        text = '{"gaps": [], "strengths": ["Python"]}{"extra": "data"}'
        result = parse_json_response(text)
        assert result == {"gaps": [], "strengths": ["Python"]}

    def test_truly_invalid_still_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_json_response("no json here at all")
