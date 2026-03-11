"""Tests for the shared API call helpers (src/api.py)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.api import call_api, parse_json_response, _strip_code_fences, _strip_preamble, _try_parse


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

    def test_invalid_json_returns_default(self):
        result = parse_json_response("not json at all")
        assert result == {}

    def test_invalid_json_custom_default(self):
        result = parse_json_response("not json at all", default={"fallback": True})
        assert result == {"fallback": True}

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

    def test_truly_invalid_returns_default(self):
        result = parse_json_response("no json here at all")
        assert result == {}

    def test_json_repair_trailing_commas(self):
        """json-repair handles trailing commas in nested structures."""
        text = '{"key": "value", "list": [1, 2, 3,],}'
        result = parse_json_response(text)
        assert result == {"key": "value", "list": [1, 2, 3]}

    def test_json_repair_single_quotes(self):
        """json-repair handles single-quoted JSON."""
        text = "{'key': 'value', 'num': 42}"
        result = parse_json_response(text)
        assert result == {"key": "value", "num": 42}

    def test_code_fence_with_language_tag(self):
        """Strips ```json fences correctly."""
        text = '```json\n{"score": 85}\n```'
        result = parse_json_response(text)
        assert result == {"score": 85}

    def test_code_fence_bare(self):
        """Strips bare ``` fences correctly."""
        text = '```\n{"score": 85}\n```'
        result = parse_json_response(text)
        assert result == {"score": 85}

    def test_code_fence_with_surrounding_prose(self):
        """Strips fences even when surrounded by prose."""
        text = 'Here is the result:\n```json\n{"score": 85}\n```\nHope this helps!'
        result = parse_json_response(text)
        assert result == {"score": 85}

    def test_json_repair_mixed_errors(self):
        """json-repair handles multiple issues at once."""
        text = "{'items': ['a', 'b',], 'count': 2,}"
        result = parse_json_response(text)
        assert result == {"items": ["a", "b"], "count": 2}


class TestStripCodeFences:
    """Tests for the _strip_code_fences helper."""

    def test_json_fence(self):
        assert _strip_code_fences('```json\n{"a": 1}\n```') == '\n{"a": 1}\n'

    def test_bare_fence(self):
        assert _strip_code_fences('```\n{"a": 1}\n```') == '\n{"a": 1}\n'

    def test_no_fence(self):
        assert _strip_code_fences('{"a": 1}') == '{"a": 1}'

    def test_multiple_fences_takes_first(self):
        text = '```json\n{"first": 1}\n```\n```json\n{"second": 2}\n```'
        result = _strip_code_fences(text)
        assert '"first"' in result


class TestTryParse:
    """Tests for the _try_parse helper."""

    def test_valid_json(self):
        assert _try_parse('{"a": 1}') == {"a": 1}

    def test_invalid_returns_none(self):
        assert _try_parse("not json") is None

    def test_extra_data_uses_raw_decode(self):
        result = _try_parse('{"a": 1}{"b": 2}')
        assert result == {"a": 1}


class TestStripPreamble:
    """Tests for the _strip_preamble helper."""

    def test_no_preamble(self):
        assert _strip_preamble('{"a": 1}') == '{"a": 1}'

    def test_array_no_preamble(self):
        assert _strip_preamble('[1, 2, 3]') == '[1, 2, 3]'

    def test_heres_the_json(self):
        result = _strip_preamble('Here\'s the JSON:\n{"a": 1}')
        assert result == '{"a": 1}'

    def test_sure_preamble(self):
        result = _strip_preamble('Sure! Here is the result:\n{"score": 85}')
        assert result == '{"score": 85}'

    def test_certainly_preamble(self):
        result = _strip_preamble('Certainly:\n{"data": true}')
        assert result == '{"data": true}'

    def test_whitespace_only_before_json(self):
        result = _strip_preamble('   \n  {"a": 1}')
        assert result == '{"a": 1}'

    def test_no_json_at_all(self):
        """Should return original text if no JSON found."""
        result = _strip_preamble("no json here")
        assert result == "no json here"

    def test_preamble_with_array(self):
        result = _strip_preamble('Here are the results: [{"a": 1}]')
        assert result == '[{"a": 1}]'


class TestPreambleStrippingIntegration:
    """Test that preamble stripping works end-to-end in parse_json_response."""

    def test_heres_the_json_parses(self):
        text = 'Here\'s the JSON output:\n{"score": 85, "match": true}'
        result = parse_json_response(text)
        assert result == {"score": 85, "match": True}

    def test_sure_with_code_fence(self):
        text = 'Sure! Here\'s the analysis:\n```json\n{"score": 85}\n```'
        result = parse_json_response(text)
        assert result == {"score": 85}

    def test_certainly_with_trailing_text(self):
        text = 'Certainly! {"score": 85}\n\nLet me know if you need anything else!'
        result = parse_json_response(text)
        assert result == {"score": 85}
