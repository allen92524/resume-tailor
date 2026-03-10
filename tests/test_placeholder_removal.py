"""Tests for placeholder skip/removal logic.

Regression tests for the bug where skipping placeholders corrupted surrounding text.
The root cause was pre-collecting match indices and using them after global cleanup
regexes shifted character positions.
"""

from unittest.mock import patch


from src.resume_reviewer import _remove_placeholder_clause, resolve_resume_placeholders


class TestRemovePlaceholderClause:
    """Unit tests for _remove_placeholder_clause (pure function, no prompts)."""

    def test_remove_by_percentage(self):
        text = "Reduced latency by [X%] through caching"
        start = text.index("[X%]")
        end = start + len("[X%]")
        result = _remove_placeholder_clause(text, start, end)
        assert result == "Reduced latency through caching"

    def test_remove_by_number(self):
        text = "Served [number] daily active users"
        start = text.index("[number]")
        end = start + len("[number]")
        result = _remove_placeholder_clause(text, start, end)
        assert result == "Served daily active users"

    def test_remove_with_following_reduction(self):
        text = "Optimized queries achieving [X%] reduction in response time"
        start = text.index("[X%]")
        end = start + len("[X%]")
        result = _remove_placeholder_clause(text, start, end)
        assert result == "Optimized queries achieving in response time"

    def test_remove_with_following_improvement(self):
        text = "Delivered [Y%] improvement in test coverage"
        start = text.index("[Y%]")
        end = start + len("[Y%]")
        result = _remove_placeholder_clause(text, start, end)
        assert result == "Delivered in test coverage"

    def test_remove_with_following_more(self):
        text = "infrastructure serving [X%] more requests"
        start = text.index("[X%]")
        end = start + len("[X%]")
        result = _remove_placeholder_clause(text, start, end)
        assert result == "infrastructure serving requests"

    def test_remove_by_percentage_at_end(self):
        text = "Reduced build time by [X%]"
        start = text.index("[X%]")
        end = start + len("[X%]")
        result = _remove_placeholder_clause(text, start, end)
        assert result == "Reduced build time"

    def test_remove_with_preposition_to(self):
        text = "Scaled system to [X%] capacity"
        start = text.index("[X%]")
        end = start + len("[X%]")
        result = _remove_placeholder_clause(text, start, end)
        assert result == "Scaled system capacity"

    def test_remove_with_preposition_from(self):
        text = "Improved coverage from [X%] baseline"
        start = text.index("[X%]")
        end = start + len("[X%]")
        result = _remove_placeholder_clause(text, start, end)
        assert result == "Improved coverage baseline"

    def test_remove_with_up_to(self):
        text = "Reduced latency up to [X%] faster"
        start = text.index("[X%]")
        end = start + len("[X%]")
        result = _remove_placeholder_clause(text, start, end)
        assert result == "Reduced latency"

    def test_remove_cleans_orphaned_comma(self):
        text = "Improved speed, by [X%], across all regions"
        start = text.index("[X%]")
        end = start + len("[X%]")
        result = _remove_placeholder_clause(text, start, end)
        assert result == "Improved speed, across all regions"

    def test_remove_cleans_comma_before_period(self):
        text = "Reduced costs by [X%]."
        start = text.index("[X%]")
        end = start + len("[X%]")
        result = _remove_placeholder_clause(text, start, end)
        assert result == "Reduced costs."

    def test_remove_preserves_surrounding_words(self):
        """Regression: 'infrastructure serving' must not become 'infrastructurg'."""
        text = "Built infrastructure serving [X%] more traffic"
        start = text.index("[X%]")
        end = start + len("[X%]")
        result = _remove_placeholder_clause(text, start, end)
        assert "infrastructure" in result
        assert "serving" in result
        assert result == "Built infrastructure serving traffic"

    def test_remove_preserves_words_around_by_clause(self):
        """Regression: 'consistency and enabling environment replication' must stay intact."""
        text = "ensuring consistency and enabling environment replication by [Y%]"
        start = text.index("[Y%]")
        end = start + len("[Y%]")
        result = _remove_placeholder_clause(text, start, end)
        assert "consistency" in result
        assert "enabling" in result
        assert "environment" in result
        assert "replication" in result
        assert result == "ensuring consistency and enabling environment replication"


class TestResolvePlaceholdersMultiple:
    """Regression tests: multiple placeholders in the same text must not corrupt."""

    def _mock_skip_all(self, text):
        """Call resolve_resume_placeholders with all 'skip' responses."""
        import re

        re.findall(r"\[([^\]]*(?:X|Y|N|number)[^\]]*)\]", text, re.IGNORECASE)
        with patch("click.prompt", return_value="skip"), patch("click.echo"):
            return resolve_resume_placeholders(text)

    def test_two_placeholders_skip_both(self):
        text = "Built infrastructure serving [X%] more traffic, ensuring consistency and enabling environment replication by [Y%]"
        result = self._mock_skip_all(text)
        assert "infrastructure" in result
        assert "serving" in result
        assert "consistency" in result
        assert "enabling" in result
        assert "environment" in result
        assert "replication" in result
        assert "[X%]" not in result
        assert "[Y%]" not in result

    def test_two_placeholders_no_corruption(self):
        """The exact regression case: surrounding words must not lose characters."""
        text = "Built infrastructure serving [X%] more traffic, ensuring consistency and enabling environment replication by [Y%]"
        result = self._mock_skip_all(text)
        # These specific corruptions were observed in the bug:
        assert (
            "infrastructurg" not in result
        )  # was corrupted from 'infrastructure serving'
        assert "consistencd" not in result  # was corrupted from 'consistency and'
        assert "environmentlication" not in result  # was corrupted

    def test_three_placeholders_skip_all(self):
        text = "Improved latency by [X%], throughput by [Y%], and uptime to [N]%"
        result = self._mock_skip_all(text)
        assert "Improved latency" in result
        assert "throughput" in result
        assert "uptime" in result
        assert "[X%]" not in result
        assert "[Y%]" not in result
        assert "[N]" not in result

    def test_mixed_skip_and_fill(self):
        """First placeholder filled, second skipped."""
        text = "Reduced latency by [X%] and improved throughput by [Y%]"
        responses = iter(["25", "skip"])
        with patch("click.prompt", side_effect=responses), patch("click.echo"):
            result = resolve_resume_placeholders(text)
        assert "25%" in result
        assert "Reduced latency by 25%" in result
        assert "improved throughput" in result
        assert "[Y%]" not in result

    def test_fill_then_skip_no_corruption(self):
        """Fill first, skip second — indices must stay valid."""
        text = "Serving [X%] more users across [number] regions worldwide"
        responses = iter(["50", "skip"])
        with patch("click.prompt", side_effect=responses), patch("click.echo"):
            result = resolve_resume_placeholders(text)
        assert "50%" in result
        assert "regions" in result
        assert "worldwide" in result
        assert "[number]" not in result

    def test_adjacent_placeholders(self):
        text = "Achieved [X%] to [Y%] improvement in performance"
        result = self._mock_skip_all(text)
        assert "Achieved" in result
        assert "performance" in result
        assert "[X%]" not in result
        assert "[Y%]" not in result

    def test_placeholder_with_existing_double_spaces(self):
        """Double spaces elsewhere must not cause index shift corruption."""
        text = "Built  infrastructure serving [X%] more traffic, enabling  replication by [Y%]"
        result = self._mock_skip_all(text)
        assert "infrastructure" in result
        assert "serving" in result
        assert "enabling" in result
        assert "replication" in result
