"""Shared API call helpers with retry logic."""

import json
import logging
import re

import anthropic
import json_repair
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
    before_sleep=lambda rs: logger.info(
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
    messages: list[dict] | None = None,
) -> str:
    """Make a Claude API call with automatic retry on transient errors.

    If *messages* is provided, it is used directly instead of building
    a single-turn message from *user_content*.

    Returns the text content of the first response block.
    """
    logger.debug("API call: model=%s, max_tokens=%d", model, max_tokens)
    with track_claude_api_call(model) as span:
        client = anthropic.Anthropic()
        msg_list = messages if messages is not None else [
            {"role": "user", "content": user_content}
        ]
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=msg_list,
            system=system,
        )
        text = message.content[0].text
        span.set_attribute("claude.response_length", len(text))
        logger.debug("API response length: %d chars", len(text))
        return text


def parse_json_response(text: str, default: dict | None = None) -> dict:
    """Extract and parse JSON from an LLM response with resilient fallbacks.

    Tries in order:
    1. Strip markdown code fences (```json ... ``` or ``` ... ```)
    2. Parse stripped text as JSON
    3. Extract first { ... } or [ ... ] block from original text
    4. Repair malformed JSON using json-repair library
    5. Use json.JSONDecoder().raw_decode() to extract first valid object
    6. Return default (empty dict) instead of crashing

    Args:
        text: Raw LLM response text.
        default: Value to return if all parsing fails. Defaults to {}.

    Returns:
        Parsed JSON as a dict (or list).
    """
    if default is None:
        default = {}

    original = text

    # Step 0: Strip non-JSON preamble (e.g. "Here's the JSON:", "Sure!", etc.)
    text = _strip_preamble(text)

    # Step 1: Strip markdown code fences
    text = _strip_code_fences(text)

    # Step 2: Try strict parse on fence-stripped text
    result = _try_parse(text.strip())
    if result is not None:
        return result

    # Step 3: Try extracting the first JSON object/array from the raw text
    brace_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", original)
    if brace_match:
        candidate = brace_match.group(1)
        result = _try_parse(candidate)
        if result is not None:
            return result

        # Step 4: Repair malformed JSON (trailing commas, single quotes, etc.)
        try:
            repaired = json_repair.repair_json(candidate, return_objects=False)
            result = _try_parse(repaired)
            if result is not None:
                return result
        except Exception:
            pass

    # Step 5: Try json-repair on the full original text
    try:
        repaired = json_repair.repair_json(original, return_objects=False)
        result = _try_parse(repaired)
        if result is not None:
            return result
    except Exception:
        pass

    # Step 6: Return default instead of crashing
    logger.error(
        "Failed to parse JSON from LLM response (length=%d). "
        "Returning default empty result. Response preview: %.200s",
        len(original),
        original,
    )
    return default


def _strip_preamble(text: str) -> str:
    """Strip non-JSON preamble that local models often prepend.

    Handles patterns like "Here's the JSON:", "Sure! Here is...",
    "Certainly:", etc. Finds the first { or [ and discards everything before it.
    """
    stripped = text.lstrip()
    # If it already starts with JSON, nothing to do
    if stripped and stripped[0] in "{[":
        return stripped
    # Find the first JSON-starting character
    for i, ch in enumerate(stripped):
        if ch in "{[":
            preamble = stripped[:i].rstrip()
            if preamble:
                logger.debug("Stripped preamble (%d chars): %.80s", len(preamble), preamble)
            return stripped[i:]
    # No JSON found — return as-is for downstream handling
    return text


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from LLM response text."""
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    return text


def _try_parse(text: str) -> dict | list | None:
    """Try to parse text as JSON, handling 'Extra data' via raw_decode.

    Returns the parsed result, or None if parsing fails.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        if "Extra data" in str(e):
            try:
                result, _ = json.JSONDecoder().raw_decode(text.strip())
                return result
            except json.JSONDecodeError:
                return None
        return None
