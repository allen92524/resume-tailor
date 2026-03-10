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
    """Extract and parse JSON from an LLM response with resilient fallbacks.

    Tries in order:
    1. Extract from ```json fences
    2. Extract from ``` fences
    3. Parse raw text as JSON
    4. Extract first { ... } or [ ... ] block
    5. Fix common issues (trailing commas, single quotes)
    Raises json.JSONDecodeError if all attempts fail.
    """
    import re

    original = text

    # Step 1-2: Try extracting from markdown code fences
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    # Step 3: Try strict parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        # Step 3b: "Extra data" means valid JSON followed by trailing text —
        # parse the first complete JSON object and ignore the rest.
        if "Extra data" in str(e):
            result, _ = json.JSONDecoder().raw_decode(text.strip())
            return result

    # Step 4: Try extracting the first JSON object/array from the raw text
    # (handles cases where the model wraps JSON in prose)
    brace_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", original)
    if brace_match:
        candidate = brace_match.group(1)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            if "Extra data" in str(e):
                result, _ = json.JSONDecoder().raw_decode(candidate)
                return result
            # Step 5: Fix common local-model issues
            fixed = _fix_json(candidate)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError as e2:
                if "Extra data" in str(e2):
                    result, _ = json.JSONDecoder().raw_decode(fixed)
                    return result

    # Final: raise with the original text for debugging
    try:
        return json.loads(original.strip())
    except json.JSONDecodeError as e:
        if "Extra data" in str(e):
            result, _ = json.JSONDecoder().raw_decode(original.strip())
            return result
        raise


def _fix_json(text: str) -> str:
    """Attempt to fix common JSON issues from local models."""
    import re

    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Replace single quotes with double quotes (but not inside strings with apostrophes)
    # Only do this if there are no double quotes at all (clearly single-quote JSON)
    if '"' not in text and "'" in text:
        text = text.replace("'", '"')
    return text
