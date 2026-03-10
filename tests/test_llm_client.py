"""Tests for the unified LLM client (src/llm_client.py)."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.llm_client import (
    call_llm,
    is_ollama_model,
    get_ollama_model_name,
    _call_ollama,
    _Spinner,
    check_ollama_ready,
    validate_ollama_model,
    warmup_ollama,
    prepare_ollama,
    normalize_response,
    _normalize_string_list,
    _detect_schema,
)


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

    @patch("src.llm_client.time.sleep")
    @patch("src.llm_client.httpx.post")
    def test_ollama_connection_error(self, mock_post, mock_sleep):
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


class TestOllamaRetryLogic:
    """Test retry behavior on timeouts and connection errors."""

    @patch("src.llm_client.time.sleep")
    @patch("src.llm_client.httpx.post")
    def test_retries_on_timeout(self, mock_post, mock_sleep):
        """Should retry up to 3 times on timeouts, then raise TimeoutError."""
        mock_post.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(TimeoutError, match="timed out after"):
            _call_ollama(model_name="qwen3.5", system="sys", user_content="hi")

        # 3 attempts total
        assert mock_post.call_count == 3
        # Sleeps between retries (2 sleeps for 3 attempts)
        assert mock_sleep.call_count == 2

    @patch("src.llm_client.time.sleep")
    @patch("src.llm_client.httpx.post")
    def test_retries_on_connection_error(self, mock_post, mock_sleep):
        """Should retry on connection errors."""
        mock_post.side_effect = httpx.ConnectError("refused")

        with pytest.raises(ConnectionError, match="Could not connect"):
            _call_ollama(model_name="qwen3.5", system="sys", user_content="hi")

        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("src.llm_client.time.sleep")
    @patch("src.llm_client.httpx.post")
    def test_succeeds_after_retry(self, mock_post, mock_sleep):
        """Should succeed if a retry works."""
        ok_response = MagicMock()
        ok_response.json.return_value = {"message": {"content": "hello"}}
        ok_response.raise_for_status = MagicMock()

        # Fail once, then succeed
        mock_post.side_effect = [
            httpx.TimeoutException("timeout"),
            ok_response,
        ]

        result = _call_ollama(model_name="qwen3.5", system="sys", user_content="hi")
        assert result == "hello"
        assert mock_post.call_count == 2
        assert mock_sleep.call_count == 1

    @patch("src.llm_client.httpx.post")
    def test_no_retry_on_http_error(self, mock_post):
        """HTTP errors (e.g. 404) should NOT be retried."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "not found"
        mock_post.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_response
        )

        with pytest.raises(RuntimeError, match="Ollama API error"):
            _call_ollama(model_name="qwen3.5", system="sys", user_content="hi")

        # Should fail immediately, no retries
        assert mock_post.call_count == 1


class TestCheckOllamaReady:
    """Test the Ollama readiness check."""

    @patch("src.llm_client.httpx.get")
    def test_ready_on_first_try(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        # Should not raise
        check_ollama_ready(base_url="http://localhost:11434")
        mock_get.assert_called_once()

    @patch("src.llm_client.OLLAMA_READY_TIMEOUT", 0)
    @patch("src.llm_client.httpx.get")
    def test_raises_after_timeout(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("refused")

        with pytest.raises(ConnectionError, match="Cannot connect to Ollama"):
            check_ollama_ready(base_url="http://localhost:11434")

    @patch("src.llm_client.time.sleep")
    @patch("src.llm_client.time.monotonic")
    @patch("src.llm_client.httpx.get")
    def test_retries_then_succeeds(self, mock_get, mock_monotonic, mock_sleep):
        """Succeeds on second attempt before timeout."""
        # Time progression: start=0, first fail check=1, retry check=2 (< 30)
        mock_monotonic.side_effect = [0, 1, 2, 3]

        ok_resp = MagicMock()
        ok_resp.raise_for_status = MagicMock()
        mock_get.side_effect = [httpx.ConnectError("refused"), ok_resp]

        check_ollama_ready(base_url="http://localhost:11434")
        assert mock_get.call_count == 2


class TestValidateOllamaModel:
    """Test model validation against Ollama's model list."""

    @patch("src.llm_client.httpx.get")
    def test_model_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "models": [
                {"name": "qwen3.5:latest"},
                {"name": "gemma3:latest"},
            ]
        }
        mock_get.return_value = mock_resp

        # Should not raise — matches "qwen3.5" against "qwen3.5:latest"
        validate_ollama_model("qwen3.5", base_url="http://localhost:11434")

    @patch("src.llm_client.httpx.get")
    def test_model_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "models": [{"name": "gemma3:latest"}]
        }
        mock_get.return_value = mock_resp

        with pytest.raises(RuntimeError, match="Model 'qwen3.5' not found"):
            validate_ollama_model("qwen3.5", base_url="http://localhost:11434")

    @patch("src.llm_client.httpx.get")
    def test_model_not_found_shows_available(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "models": [
                {"name": "gemma3:latest"},
                {"name": "llama3:8b"},
            ]
        }
        mock_get.return_value = mock_resp

        with pytest.raises(RuntimeError, match="gemma3:latest, llama3:8b"):
            validate_ollama_model("qwen3.5", base_url="http://localhost:11434")

    @patch("src.llm_client.httpx.get")
    def test_model_not_found_shows_pull_command(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"models": []}
        mock_get.return_value = mock_resp

        with pytest.raises(RuntimeError, match="ollama pull qwen3.5"):
            validate_ollama_model("qwen3.5", base_url="http://localhost:11434")

    @patch("src.llm_client.httpx.get")
    def test_exact_name_match_with_tag(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "models": [{"name": "qwen3.5:latest"}]
        }
        mock_get.return_value = mock_resp

        # Exact match with tag should work too
        validate_ollama_model("qwen3.5:latest", base_url="http://localhost:11434")

    @patch("src.llm_client.httpx.get")
    def test_connection_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("refused")

        with pytest.raises(ConnectionError, match="Cannot connect"):
            validate_ollama_model("qwen3.5", base_url="http://localhost:11434")


class TestWarmupOllama:
    """Test the warm-up (model preloading) step."""

    @patch("src.llm_client.httpx.post")
    def test_warmup_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        # Should not raise
        warmup_ollama("qwen3.5", base_url="http://localhost:11434")
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        assert payload["model"] == "qwen3.5"
        assert payload["messages"][0]["content"] == "hi"

    @patch("src.llm_client.httpx.post")
    def test_warmup_timeout_continues(self, mock_post):
        """Warm-up timeout should warn but not raise."""
        mock_post.side_effect = httpx.TimeoutException("timed out")

        # Should NOT raise — warm-up timeout is non-fatal
        warmup_ollama("qwen3.5", base_url="http://localhost:11434")

    @patch("src.llm_client.httpx.post")
    def test_warmup_connection_error_raises(self, mock_post):
        """Warm-up connection error should raise."""
        mock_post.side_effect = httpx.ConnectError("refused")

        with pytest.raises(ConnectionError, match="Cannot connect"):
            warmup_ollama("qwen3.5", base_url="http://localhost:11434")


class TestPrepareOllama:
    """Test the full Ollama startup sequence."""

    @patch("src.llm_client.warmup_ollama")
    @patch("src.llm_client.validate_ollama_model")
    @patch("src.llm_client.check_ollama_ready")
    def test_full_sequence(self, mock_ready, mock_validate, mock_warmup):
        prepare_ollama("ollama:qwen3.5", base_url="http://localhost:11434")

        mock_ready.assert_called_once_with("http://localhost:11434")
        mock_validate.assert_called_once_with("qwen3.5", "http://localhost:11434")
        mock_warmup.assert_called_once_with("qwen3.5", "http://localhost:11434")

    @patch("src.llm_client.warmup_ollama")
    @patch("src.llm_client.validate_ollama_model")
    @patch("src.llm_client.check_ollama_ready")
    def test_stops_on_ready_failure(self, mock_ready, mock_validate, mock_warmup):
        mock_ready.side_effect = ConnectionError("not reachable")

        with pytest.raises(ConnectionError):
            prepare_ollama("ollama:qwen3.5")

        mock_validate.assert_not_called()
        mock_warmup.assert_not_called()

    @patch("src.llm_client.warmup_ollama")
    @patch("src.llm_client.validate_ollama_model")
    @patch("src.llm_client.check_ollama_ready")
    def test_stops_on_model_not_found(self, mock_ready, mock_validate, mock_warmup):
        mock_validate.side_effect = RuntimeError("Model not found")

        with pytest.raises(RuntimeError):
            prepare_ollama("ollama:qwen3.5")

        mock_warmup.assert_not_called()


class TestNormalizeStringList:
    """Test _normalize_string_list for various input formats."""

    def test_plain_strings(self):
        result = _normalize_string_list(["foo", "bar"])
        assert result == ["foo", "bar"]

    def test_dict_with_summary(self):
        items = [
            {"id": 1, "category": "Python", "summary": "Strong Python skills"},
            {"id": 2, "category": "AWS", "summary": "AWS experience"},
        ]
        result = _normalize_string_list(items)
        assert result == ["Strong Python skills", "AWS experience"]

    def test_dict_with_description(self):
        items = [{"description": "Kubernetes expertise"}]
        result = _normalize_string_list(items)
        assert result == ["Kubernetes expertise"]

    def test_dict_with_text(self):
        items = [{"text": "Some text"}]
        result = _normalize_string_list(items)
        assert result == ["Some text"]

    def test_dict_fallback_joins_values(self):
        items = [{"foo": "hello", "bar": "world"}]
        result = _normalize_string_list(items)
        assert result == ["hello; world"]

    def test_mixed_types(self):
        items = ["plain string", {"summary": "dict string"}, 42]
        result = _normalize_string_list(items)
        assert result == ["plain string", "dict string", "42"]

    def test_empty_list(self):
        assert _normalize_string_list([]) == []


class TestDetectSchema:
    """Test auto-detection of response schema."""

    def test_gap_analysis(self):
        assert _detect_schema({"gaps": [], "strengths": []}) == "gap_analysis"

    def test_compatibility(self):
        assert _detect_schema({"match_score": 75}) == "compatibility"

    def test_resume_review(self):
        assert _detect_schema({"overall_score": 80, "strengths": []}) == "resume_review"

    def test_jd_analysis(self):
        assert _detect_schema({"required_skills": []}) == "jd_analysis"

    def test_resume_content(self):
        assert _detect_schema({"experience": [], "summary": "..."}) == "resume_content"

    def test_unknown(self):
        assert _detect_schema({"random": "data"}) is None


class TestNormalizeGapAnalysis:
    """Test gap analysis normalization for both Claude and Ollama formats."""

    def test_claude_format_passthrough(self):
        """Claude returns the expected format — normalization is a no-op."""
        data = {
            "gaps": [
                {"skill": "Go", "question": "Do you have Go experience?"},
                {"skill": "K8s", "question": "Kubernetes experience?"},
            ],
            "strengths": [
                "Strong Python skills",
                "AWS experience",
            ],
        }
        result = normalize_response(data, schema="gap_analysis")
        assert result["gaps"] == data["gaps"]
        assert result["strengths"] == data["strengths"]

    def test_ollama_strengths_as_dicts(self):
        """Ollama sometimes returns strengths as list of objects."""
        data = {
            "gaps": [{"skill": "Go", "question": "Go experience?"}],
            "strengths": [
                {"id": 1, "category": "Python", "summary": "Strong Python proficiency"},
                {"id": 2, "category": "AWS", "summary": "Extensive AWS experience"},
            ],
        }
        result = normalize_response(data, schema="gap_analysis")
        assert result["strengths"] == [
            "Strong Python proficiency",
            "Extensive AWS experience",
        ]
        assert result["gaps"] == [{"skill": "Go", "question": "Go experience?"}]

    def test_ollama_gaps_alternate_keys(self):
        """Ollama may use different keys like 'name' and 'follow_up_question'."""
        data = {
            "gaps": [
                {"name": "Go", "follow_up_question": "Any Go experience?"},
                {"area": "K8s", "description": "Tell me about K8s."},
            ],
            "strengths": ["Already good at Python"],
        }
        result = normalize_response(data, schema="gap_analysis")
        assert result["gaps"] == [
            {"skill": "Go", "question": "Any Go experience?"},
            {"skill": "K8s", "question": "Tell me about K8s."},
        ]
        assert result["strengths"] == ["Already good at Python"]

    def test_gaps_as_strings(self):
        """Edge case: Ollama returns gaps as plain strings."""
        data = {
            "gaps": ["Go programming", "Kubernetes"],
            "strengths": ["Python"],
        }
        result = normalize_response(data, schema="gap_analysis")
        assert result["gaps"] == [
            {"skill": "Go programming", "question": ""},
            {"skill": "Kubernetes", "question": ""},
        ]

    def test_empty_response(self):
        data = {"gaps": [], "strengths": []}
        result = normalize_response(data, schema="gap_analysis")
        assert result == {"gaps": [], "strengths": []}

    def test_auto_detects_schema(self):
        """normalize_response auto-detects gap_analysis schema."""
        data = {
            "gaps": [{"skill": "Go", "question": "?"}],
            "strengths": [{"summary": "Python"}],
        }
        result = normalize_response(data)
        assert result["strengths"] == ["Python"]


class TestNormalizeCompatibility:
    """Test compatibility assessment normalization."""

    def test_claude_format(self):
        data = {
            "match_score": 75,
            "strong_matches": ["Python", "AWS"],
            "addressable_gaps": ["Go"],
            "missing": ["Rust"],
            "recommendation": "Good fit",
        }
        result = normalize_response(data, schema="compatibility")
        assert result["strong_matches"] == ["Python", "AWS"]

    def test_ollama_dicts_in_lists(self):
        data = {
            "match_score": 60,
            "strong_matches": [
                {"name": "Python", "description": "Strong Python skills"},
            ],
            "addressable_gaps": [{"summary": "Could learn Go"}],
            "missing": ["Rust"],
            "recommendation": "Apply",
        }
        result = normalize_response(data, schema="compatibility")
        assert result["strong_matches"] == ["Strong Python skills"]
        assert result["addressable_gaps"] == ["Could learn Go"]
        assert result["missing"] == ["Rust"]


class TestNormalizeResumeReview:
    """Test resume review normalization."""

    def test_claude_format(self):
        data = {
            "overall_score": 72,
            "strengths": ["Clear formatting", "Good keywords"],
            "missing_keywords": ["agile", "scrum"],
        }
        result = normalize_response(data, schema="resume_review")
        assert result["strengths"] == ["Clear formatting", "Good keywords"]

    def test_ollama_dicts(self):
        data = {
            "overall_score": 65,
            "strengths": [{"summary": "Clear formatting"}],
            "missing_keywords": [{"text": "agile"}],
        }
        result = normalize_response(data, schema="resume_review")
        assert result["strengths"] == ["Clear formatting"]
        assert result["missing_keywords"] == ["agile"]


class TestNormalizeJdAnalysis:
    """Test JD analysis normalization."""

    def test_claude_format(self):
        data = {
            "required_skills": ["Python", "AWS"],
            "preferred_skills": ["Go"],
            "key_responsibilities": ["Build services"],
            "keywords": ["microservices"],
            "culture_signals": ["fast-paced"],
        }
        result = normalize_response(data, schema="jd_analysis")
        assert result == data

    def test_ollama_dicts(self):
        data = {
            "required_skills": [{"name": "Python"}, {"name": "AWS"}],
            "preferred_skills": ["Go"],
            "key_responsibilities": [{"description": "Build services"}],
            "keywords": ["microservices"],
            "culture_signals": [{"text": "fast-paced"}],
        }
        result = normalize_response(data, schema="jd_analysis")
        assert result["required_skills"] == ["Python", "AWS"]
        assert result["key_responsibilities"] == ["Build services"]
        assert result["culture_signals"] == ["fast-paced"]


class TestNormalizeResumeContent:
    """Test resume content normalization."""

    def test_certifications_as_strings(self):
        data = {
            "experience": [],
            "summary": "Engineer",
            "certifications": ["CKA", "AWS SAA"],
        }
        result = normalize_response(data, schema="resume_content")
        assert result["certifications"] == ["CKA", "AWS SAA"]

    def test_certifications_as_dicts(self):
        data = {
            "experience": [],
            "summary": "Engineer",
            "certifications": [
                {"name": "CKA", "issuer": "CNCF"},
                {"name": "AWS SAA"},
            ],
        }
        result = normalize_response(data, schema="resume_content")
        assert result["certifications"] == ["CKA", "AWS SAA"]


class TestSpinner:
    """Test the background spinner utility."""

    def test_spinner_starts_and_stops(self):
        """Spinner should start and stop without errors."""
        spinner = _Spinner("Testing...")
        spinner.start()
        import time

        time.sleep(0.1)
        spinner.stop()

    def test_spinner_context_manager(self):
        """Spinner should work as a context manager."""
        import time

        with _Spinner("Testing..."):
            time.sleep(0.1)

    def test_spinner_stop_is_idempotent(self):
        """Calling stop multiple times should not raise."""
        spinner = _Spinner("Testing...")
        spinner.start()
        spinner.stop()
        spinner.stop()  # second stop should not raise


class TestPrepareOllamaHint:
    """Test that prepare_ollama shows the time estimate hint."""

    @patch("src.llm_client.warmup_ollama")
    @patch("src.llm_client.validate_ollama_model")
    @patch("src.llm_client.check_ollama_ready")
    def test_shows_time_hint(self, mock_ready, mock_validate, mock_warmup, capsys):
        prepare_ollama("ollama:qwen3.5", base_url="http://localhost:11434")

        captured = capsys.readouterr()
        assert "2-5 minutes" in captured.out
        assert "--model claude" in captured.out
