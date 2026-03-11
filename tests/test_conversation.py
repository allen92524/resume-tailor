"""Tests for the conversational Q&A engine."""

import json
from unittest.mock import patch

from src.conversation import conversational_qa, generate_improved_bullet, confirm_bullet


class TestConversationalQA:
    def test_user_skips_immediately(self):
        """Empty input returns None."""
        with patch("src.conversation.click.prompt", return_value=""):
            result = conversational_qa(
                context_type="resume weakness",
                context_description="Vague bullet points",
                initial_question="Can you add metrics?",
                model="claude",
            )
        assert result is None

    def test_good_answer_accepted(self):
        """LLM returns accept on first round — returns the answer."""
        llm_response = json.dumps({
            "action": "accept",
            "message": "Great details!",
            "acknowledgment": "Nice, that's very specific.",
        })

        with patch("src.conversation.click.prompt", return_value="I reduced deploy time by 40%"), \
             patch("src.conversation.call_llm", return_value=llm_response), \
             patch("src.conversation.click.echo"):
            result = conversational_qa(
                context_type="resume weakness",
                context_description="Missing metrics",
                initial_question="What metrics can you add?",
                model="claude",
            )

        assert result == "I reduced deploy time by 40%"

    def test_followup_then_accept(self):
        """Vague answer triggers follow-up, then good answer is accepted."""
        followup_response = json.dumps({
            "action": "ask",
            "message": "How many servers were involved?",
            "acknowledgment": "Got it.",
        })
        accept_response = json.dumps({
            "action": "accept",
            "message": "Perfect, that's enough detail.",
            "acknowledgment": "Great specifics!",
        })

        prompt_returns = ["not sure", "about 50 servers"]

        with patch("src.conversation.click.prompt", side_effect=prompt_returns), \
             patch("src.conversation.call_llm", side_effect=[followup_response, accept_response]), \
             patch("src.conversation.click.echo"):
            result = conversational_qa(
                context_type="resume weakness",
                context_description="Vague infrastructure work",
                initial_question="Can you describe the scale?",
                model="claude",
            )

        assert "not sure" in result
        assert "50 servers" in result

    def test_max_followups_reached(self):
        """Hits max follow-ups limit, returns accumulated answers."""
        ask_response = json.dumps({
            "action": "ask",
            "message": "Can you be more specific?",
            "acknowledgment": "Thanks.",
        })

        # 1 initial + 2 follow-ups (max_followups=2)
        prompt_returns = ["some stuff", "more stuff", "even more"]

        with patch("src.conversation.click.prompt", side_effect=prompt_returns), \
             patch("src.conversation.call_llm", side_effect=[ask_response, ask_response]), \
             patch("src.conversation.click.echo"):
            result = conversational_qa(
                context_type="resume weakness",
                context_description="Unclear impact",
                initial_question="What was the impact?",
                model="claude",
                max_followups=2,
            )

        assert "some stuff" in result
        assert "more stuff" in result
        assert "even more" in result

    def test_give_up_gracefully(self):
        """LLM gives up after user can't answer."""
        give_up_response = json.dumps({
            "action": "give_up",
            "message": "No worries, we'll work with what we have.",
        })

        with patch("src.conversation.click.prompt", return_value="I really don't know"), \
             patch("src.conversation.call_llm", return_value=give_up_response), \
             patch("src.conversation.click.echo"):
            result = conversational_qa(
                context_type="resume weakness",
                context_description="Missing metrics",
                initial_question="What metrics can you add?",
                model="claude",
            )

        assert result == "I really don't know"

    def test_followup_skip_stops_loop(self):
        """If user skips a follow-up (empty input), the loop stops."""
        ask_response = json.dumps({
            "action": "ask",
            "message": "Can you elaborate?",
            "acknowledgment": "Okay.",
        })

        prompt_returns = ["initial answer", ""]  # skip follow-up

        with patch("src.conversation.click.prompt", side_effect=prompt_returns), \
             patch("src.conversation.call_llm", return_value=ask_response), \
             patch("src.conversation.click.echo"):
            result = conversational_qa(
                context_type="skill gap",
                context_description="Kubernetes",
                initial_question="Do you have K8s experience?",
                model="claude",
            )

        assert result == "initial answer"

    def test_llm_failure_returns_current_answers(self):
        """If LLM call fails, returns what we have so far."""
        with patch("src.conversation.click.prompt", return_value="my answer"), \
             patch("src.conversation.call_llm", side_effect=Exception("API error")), \
             patch("src.conversation.click.echo"):
            result = conversational_qa(
                context_type="resume weakness",
                context_description="Missing metrics",
                initial_question="What metrics?",
                model="claude",
            )

        assert result == "my answer"


class TestGenerateImprovedBullet:
    def test_calls_llm_with_correct_prompt(self):
        """Verifies the LLM is called with the right parameters."""
        with patch("src.conversation.call_llm", return_value="Improved bullet text") as mock_llm:
            result = generate_improved_bullet(
                original_bullet="Managed servers",
                weakness_context="Missing metrics",
                user_answers="50 servers, reduced downtime by 30%",
                model="claude",
            )

        assert result == "Improved bullet text"
        assert mock_llm.called
        call_kwargs = mock_llm.call_args[1]
        assert "Managed servers" in call_kwargs["user_content"]
        assert "50 servers" in call_kwargs["user_content"]

    def test_strips_quotes(self):
        """LLM sometimes wraps response in quotes — they should be stripped."""
        with patch("src.conversation.call_llm", return_value='"Improved bullet"'):
            result = generate_improved_bullet(
                original_bullet="Original",
                weakness_context="Weak",
                user_answers="Details",
                model="claude",
            )

        assert result == "Improved bullet"


class TestConfirmBullet:
    def test_yes(self):
        """User accepts the bullet."""
        with patch("src.conversation.click.prompt", return_value="y"), \
             patch("src.conversation.click.echo"):
            result = confirm_bullet("Great bullet text")
        assert result == "Great bullet text"

    def test_enter_defaults_to_yes(self):
        """Empty input defaults to yes."""
        with patch("src.conversation.click.prompt", return_value=""), \
             patch("src.conversation.click.echo"):
            result = confirm_bullet("Great bullet text")
        assert result == "Great bullet text"

    def test_no(self):
        """User rejects the bullet."""
        with patch("src.conversation.click.prompt", return_value="n"), \
             patch("src.conversation.click.echo"):
            result = confirm_bullet("Bad bullet text")
        assert result is None

    def test_edit(self):
        """User edits the bullet."""
        prompt_returns = ["e", "My edited bullet"]
        with patch("src.conversation.click.prompt", side_effect=prompt_returns), \
             patch("src.conversation.click.echo"):
            result = confirm_bullet("Original bullet")
        assert result == "My edited bullet"

    def test_edit_empty_returns_none(self):
        """Empty edit returns None."""
        prompt_returns = ["e", ""]
        with patch("src.conversation.click.prompt", side_effect=prompt_returns), \
             patch("src.conversation.click.echo"):
            result = confirm_bullet("Original bullet")
        assert result is None
