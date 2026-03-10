"""Shared API call helpers with retry logic."""

import json
import logging

import anthropic
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .config import RETRY_MAX_ATTEMPTS, RETRY_MIN_WAIT, RETRY_MAX_WAIT
from .telemetry import track_claude_api_call

logger = logging.getLogger(__name__)

_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)


@retry(
    stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
    retry=retry_if_exception_type(_RETRYABLE),
    before_sleep=lambda rs: logger.warning(
        "API call failed (%s), retrying in %ds (attempt %d/%d)...",
        rs.outcome.exception().__class__.__name__,
        rs.next_action.sleep,
        rs.attempt_number,
        RETRY_MAX_ATTEMPTS,
    ),
)
def call_api(
    *,
    model: str,
    max_tokens: int,
    system: str,
    user_content: str,
) -> str:
    """Make a Claude API call with automatic retry on transient errors.

    Returns the text content of the first response block.
    """
    logger.debug("API call: model=%s, max_tokens=%d", model, max_tokens)
    with track_claude_api_call(model) as span:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": user_content}],
            system=system,
        )
        text = message.content[0].text
        span.set_attribute("claude.response_length", len(text))
        logger.debug("API response length: %d chars", len(text))
        return text


def parse_json_response(text: str) -> dict:
    """Extract and parse JSON from Claude's response, handling code blocks."""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())
