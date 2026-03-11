"""Unified LLM client that wraps both Claude API and Ollama."""

import logging
import sys
import threading
import time

import click
import httpx

from .config import (
    CLAUDE_MODEL,
    DEFAULT_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_TIMEOUT,
    OLLAMA_RETRY_ATTEMPTS,
    OLLAMA_RETRY_DELAY,
    OLLAMA_READY_TIMEOUT,
    OLLAMA_HARD_TIMEOUT,
    OLLAMA_MIN_RESPONSE_LENGTH,
    OLLAMA_MAX_RESPONSE_LENGTH,
    OLLAMA_CONTEXT_WARN_TOKENS,
)

logger = logging.getLogger(__name__)


def is_ollama_model(model: str) -> bool:
    """Check if a model string refers to an Ollama model."""
    return model.startswith("ollama:")


def get_ollama_model_name(model: str) -> str:
    """Extract the Ollama model name from an 'ollama:name' string."""
    return model.split(":", 1)[1]


def list_ollama_models(base_url: str = OLLAMA_BASE_URL) -> list[dict]:
    """Fetch available models from Ollama's /api/tags endpoint.

    Returns a list of dicts with 'name' and 'size' keys, or an empty list
    if Ollama is not reachable.
    """
    url = f"{base_url}/api/tags"
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
        return []

    data = resp.json()
    models = []
    for m in data.get("models", []):
        name = m.get("name", "")
        size_bytes = m.get("size", 0)
        size_gb = size_bytes / (1024 ** 3) if size_bytes else 0
        models.append({"name": name, "size_gb": round(size_gb, 1)})
    return models



def check_ollama_ready(base_url: str = OLLAMA_BASE_URL) -> None:
    """Ping Ollama's /api/tags endpoint, retrying up to OLLAMA_READY_TIMEOUT seconds.

    Raises ConnectionError if Ollama is not reachable after the timeout.
    """
    url = f"{base_url}/api/tags"
    deadline = time.monotonic() + OLLAMA_READY_TIMEOUT
    attempt = 0

    while True:
        attempt += 1
        try:
            resp = httpx.get(url, timeout=5.0)
            resp.raise_for_status()
            logger.debug("Ollama is ready (attempt %d)", attempt)
            return
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            if time.monotonic() >= deadline:
                raise ConnectionError(
                    f"Cannot connect to Ollama at {base_url}. Is it running? "
                    "Start it with: ollama serve"
                ) from e
            remaining = int(deadline - time.monotonic())
            click.echo(
                f"Waiting for Ollama to be ready... (retrying, {remaining}s left)"
            )
            time.sleep(2)


def validate_ollama_model(
    model_name: str, base_url: str = OLLAMA_BASE_URL
) -> None:
    """Check if the requested model is available in Ollama.

    Raises RuntimeError with helpful message if the model is not found.
    """
    url = f"{base_url}/api/tags"
    try:
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        raise ConnectionError(
            f"Cannot connect to Ollama at {base_url}. Is it running?"
        ) from e

    data = resp.json()
    models = data.get("models", [])
    available_names = []
    for m in models:
        name = m.get("name", "")
        available_names.append(name)
        # Match with or without tag suffix (e.g. "qwen3.5" matches "qwen3.5:latest")
        base = name.split(":")[0] if ":" in name else name
        if name == model_name or base == model_name:
            logger.debug("Model %s found in Ollama", model_name)
            return

    available_str = ", ".join(available_names) if available_names else "(none)"
    raise RuntimeError(
        f"Model '{model_name}' not found. "
        f"Available models: {available_str}. "
        f"Pull it with: ollama pull {model_name}"
    )


def warmup_ollama(
    model_name: str, base_url: str = OLLAMA_BASE_URL
) -> None:
    """Send a tiny prompt to Ollama to force the model to load into memory.

    This prevents the first real call from timing out while the model loads.
    """
    click.echo(
        f"Loading model {model_name} into memory... "
        "(this may take 30-60s on first run)"
    )
    url = f"{base_url}/api/chat"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
    }
    start = time.monotonic()
    try:
        resp = httpx.post(url, json=payload, timeout=float(OLLAMA_TIMEOUT))
        resp.raise_for_status()
        elapsed = time.monotonic() - start
        click.echo(f"Model loaded. ({elapsed:.0f}s)")
    except httpx.TimeoutException:
        elapsed = time.monotonic() - start
        click.echo(
            f"Warm-up timed out after {elapsed:.0f}s. "
            "The model may still be loading — continuing anyway."
        )
    except httpx.ConnectError as e:
        raise ConnectionError(
            f"Cannot connect to Ollama at {base_url}. Is it running?"
        ) from e


def prepare_ollama(model: str, base_url: str = OLLAMA_BASE_URL) -> None:
    """Run Ollama startup sequence: readiness check, model validation, warm-up.

    Call this once before the main flow when using an Ollama model.
    Also shows a Docker CPU tip if running in a container.
    """
    model_name = get_ollama_model_name(model)

    # Docker CPU tip
    _show_docker_tip(model_name)

    click.echo("Checking Ollama connectivity...")
    check_ollama_ready(base_url)
    click.echo("Ollama is ready.")

    click.echo(f"Checking model availability: {model_name}")
    validate_ollama_model(model_name, base_url)

    warmup_ollama(model_name, base_url)

    click.echo(
        click.style(
            "Note: Local model inference may take 2-5 minutes per step. "
            "For faster results, use Claude API with --model claude",
            fg="yellow",
        )
    )


class _Spinner:
    """Background spinner that shows elapsed time during long operations."""

    _FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, message: str) -> None:
        self._message = message
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_time = 0.0

    def start(self) -> None:
        self._start_time = time.monotonic()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        # Clear the spinner line
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()

    def _run(self) -> None:
        idx = 0
        while not self._stop.wait(timeout=1.0):
            elapsed = int(time.monotonic() - self._start_time)
            frame = self._FRAMES[idx % len(self._FRAMES)]
            sys.stderr.write(f"\r{frame} {self._message} ({elapsed}s elapsed)")
            sys.stderr.flush()
            idx += 1

    def __enter__(self) -> "_Spinner":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()


def _show_docker_tip(model_name: str) -> None:
    """Show a tip about smaller models when running in Docker without GPU."""
    import os

    # /.dockerenv exists inside Docker containers
    if os.path.exists("/.dockerenv") and not os.environ.get("NVIDIA_VISIBLE_DEVICES"):
        click.echo(
            click.style(
                "Tip: Running in Docker without GPU. For faster results, "
                "try a smaller model like ollama:gemma3 or ollama:qwen3.5:1.5b",
                fg="yellow",
            )
        )


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token for English text."""
    return len(text) // 4


def check_context_window(system: str, user_content: str) -> None:
    """Warn if estimated token count exceeds the small-model context limit."""
    total = estimate_tokens(system) + estimate_tokens(user_content)
    if total > OLLAMA_CONTEXT_WARN_TOKENS:
        click.echo(
            click.style(
                f"Warning: Estimated input size (~{total} tokens) exceeds "
                f"{OLLAMA_CONTEXT_WARN_TOKENS} tokens. "
                "This may be too long for small local models. "
                "Consider using Claude API (--model claude) or a larger model.",
                fg="yellow",
            )
        )
    logger.debug("Estimated token count: %d", total)


def validate_response_length(text: str, model_name: str) -> None:
    """Check if response length is within expected bounds.

    Raises RuntimeError if the response is suspiciously short or long.
    """
    length = len(text)
    if length < OLLAMA_MIN_RESPONSE_LENGTH:
        raise RuntimeError(
            f"Response from {model_name} is too short ({length} chars). "
            "The model may not have understood the prompt. Retrying..."
        )
    if length > OLLAMA_MAX_RESPONSE_LENGTH:
        raise RuntimeError(
            f"Response from {model_name} is too long ({length} chars). "
            "The output may be corrupted. Retrying..."
        )


def _call_ollama(
    *,
    model_name: str,
    system: str,
    user_content: str,
    messages: list[dict] | None = None,
    base_url: str = OLLAMA_BASE_URL,
) -> str:
    """Call the Ollama REST API with retry logic and elapsed-time progress.

    If *messages* is provided, it is prepended with the system message and
    used directly instead of building a single-turn message from *user_content*.

    Retries up to OLLAMA_RETRY_ATTEMPTS times on connection errors, timeouts,
    and response length violations. Enforces a hard timeout of
    OLLAMA_HARD_TIMEOUT seconds per call.
    """
    url = f"{base_url}/api/chat"
    if messages is not None:
        msg_list = [{"role": "system", "content": system}] + messages
    else:
        msg_list = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]
    payload = {
        "model": model_name,
        "messages": msg_list,
        "stream": False,
    }

    # Use the stricter of OLLAMA_TIMEOUT and OLLAMA_HARD_TIMEOUT
    effective_timeout = min(float(OLLAMA_TIMEOUT), float(OLLAMA_HARD_TIMEOUT))

    logger.debug("Ollama request: model=%s, url=%s", model_name, url)

    last_error: Exception | None = None
    for attempt in range(1, OLLAMA_RETRY_ATTEMPTS + 1):
        spinner = _Spinner(f"Processing with {model_name}...")
        try:
            spinner.start()
            response = httpx.post(
                url, json=payload, timeout=effective_timeout
            )
            spinner.stop()
            response.raise_for_status()

            data = response.json()
            text = data.get("message", {}).get("content", "")
            if not text:
                raise RuntimeError(
                    f"Empty response from Ollama model '{model_name}'"
                )

            # Validate response length
            validate_response_length(text, model_name)

            logger.debug("Ollama response length: %d chars", len(text))
            return text

        except httpx.ConnectError as e:
            spinner.stop()
            last_error = e
            if attempt < OLLAMA_RETRY_ATTEMPTS:
                click.echo(
                    f"Cannot connect to Ollama. Is it running? "
                    f"Retrying in {OLLAMA_RETRY_DELAY}s... "
                    f"(attempt {attempt + 1}/{OLLAMA_RETRY_ATTEMPTS})"
                )
                time.sleep(OLLAMA_RETRY_DELAY)
            else:
                raise ConnectionError(
                    f"Could not connect to Ollama at {base_url}. "
                    "Is Ollama running? Start it with: ollama serve"
                ) from e

        except httpx.TimeoutException as e:
            spinner.stop()
            last_error = e
            if attempt < OLLAMA_RETRY_ATTEMPTS:
                click.echo(
                    f"Request timed out, retrying... "
                    f"(attempt {attempt + 1}/{OLLAMA_RETRY_ATTEMPTS})"
                )
                time.sleep(OLLAMA_RETRY_DELAY)
            else:
                raise TimeoutError(
                    f"Ollama request timed out after {effective_timeout:.0f}s "
                    f"({OLLAMA_RETRY_ATTEMPTS} attempts). "
                    f"Try increasing OLLAMA_TIMEOUT (currently {OLLAMA_TIMEOUT}s) "
                    f"or use a smaller model."
                ) from e

        except RuntimeError as e:
            spinner.stop()
            # Response length errors are retryable
            if "too short" in str(e) or "too long" in str(e):
                last_error = e
                if attempt < OLLAMA_RETRY_ATTEMPTS:
                    click.echo(
                        f"{e} "
                        f"(attempt {attempt}/{OLLAMA_RETRY_ATTEMPTS})"
                    )
                    time.sleep(OLLAMA_RETRY_DELAY)
                    continue
                raise
            # HTTPStatusError-wrapped RuntimeErrors and others — don't retry
            raise

        except httpx.HTTPStatusError as e:
            spinner.stop()
            raise RuntimeError(
                f"Ollama API error: {e.response.status_code} - {e.response.text}"
            ) from e

    # Should not be reached, but just in case
    raise RuntimeError(f"Ollama call failed after {OLLAMA_RETRY_ATTEMPTS} attempts") from last_error


def normalize_response(data: dict, schema: str | None = None) -> dict:
    """Normalize an LLM JSON response into the expected format.

    Different models (Claude vs Ollama) sometimes return slightly different
    structures for the same prompt. This function converts any recognized
    variant into the canonical format that the rest of the code expects.

    Args:
        data: Parsed JSON dict from an LLM response.
        schema: Which response schema to normalize. Currently supported:
                "gap_analysis", "jd_analysis", "compatibility",
                "resume_content", "resume_review".
                If None, auto-detects based on keys present.

    Returns:
        The normalized dict.
    """
    if schema is None:
        schema = _detect_schema(data)

    if schema == "gap_analysis":
        data = _normalize_gap_analysis(data)
    elif schema == "compatibility":
        data = _normalize_compatibility(data)
    elif schema == "resume_review":
        data = _normalize_resume_review(data)
    elif schema == "jd_analysis":
        data = _normalize_jd_analysis(data)
    elif schema == "resume_content":
        data = _normalize_resume_content(data)

    return data


def _detect_schema(data: dict) -> str | None:
    """Auto-detect the response schema from its keys."""
    keys = set(data.keys())
    if "gaps" in keys or "strengths" in keys and "match_score" not in keys:
        if "overall_score" in keys:
            return "resume_review"
        return "gap_analysis"
    if "match_score" in keys:
        return "compatibility"
    if "overall_score" in keys:
        return "resume_review"
    if "required_skills" in keys or "key_responsibilities" in keys:
        return "jd_analysis"
    if "experience" in keys and "summary" in keys:
        return "resume_content"
    return None


def _normalize_string_list(items: list) -> list[str]:
    """Convert a list that may contain dicts to a list of strings.

    Handles Ollama returning e.g. [{"id": 1, "summary": "..."}] instead of
    ["..."].  Tries keys: summary, description, text, issue, name, then str().
    """
    result: list[str] = []
    for item in items:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            for key in ("summary", "description", "text", "issue", "name"):
                if key in item:
                    result.append(str(item[key]))
                    break
            else:
                # Last resort: join all string values
                vals = [str(v) for v in item.values() if isinstance(v, str)]
                result.append("; ".join(vals) if vals else str(item))
        else:
            result.append(str(item))
    return result


def _normalize_gap_entry(gap: dict) -> dict:
    """Normalize a single gap entry to have 'skill' and 'question' keys."""
    # Handle alternate key names Ollama might use
    skill = gap.get("skill") or gap.get("name") or gap.get("area") or ""
    question = (
        gap.get("question")
        or gap.get("follow_up")
        or gap.get("follow_up_question")
        or gap.get("description")
        or ""
    )
    return {"skill": str(skill), "question": str(question)}


def _normalize_gap_analysis(data: dict) -> dict:
    """Normalize gap analysis response."""
    # Normalize gaps list
    raw_gaps = data.get("gaps", [])
    normalized_gaps = []
    for g in raw_gaps:
        if isinstance(g, dict):
            normalized_gaps.append(_normalize_gap_entry(g))
        elif isinstance(g, str):
            normalized_gaps.append({"skill": g, "question": ""})

    # Normalize strengths list (may be dicts instead of strings)
    raw_strengths = data.get("strengths", [])
    normalized_strengths = _normalize_string_list(raw_strengths)

    return {"gaps": normalized_gaps, "strengths": normalized_strengths}


def _normalize_compatibility(data: dict) -> dict:
    """Normalize compatibility assessment response."""
    for key in ("strong_matches", "addressable_gaps", "missing"):
        if key in data and isinstance(data[key], list):
            data[key] = _normalize_string_list(data[key])
    return data


def _normalize_resume_review(data: dict) -> dict:
    """Normalize resume review response."""
    if "strengths" in data and isinstance(data["strengths"], list):
        data["strengths"] = _normalize_string_list(data["strengths"])
    if "missing_keywords" in data and isinstance(data["missing_keywords"], list):
        data["missing_keywords"] = _normalize_string_list(data["missing_keywords"])
    return data


def _normalize_jd_analysis(data: dict) -> dict:
    """Normalize JD analysis response."""
    for key in (
        "required_skills",
        "preferred_skills",
        "key_responsibilities",
        "keywords",
        "culture_signals",
    ):
        if key in data and isinstance(data[key], list):
            data[key] = _normalize_string_list(data[key])
    return data


def _normalize_resume_content(data: dict) -> dict:
    """Normalize resume content response."""
    if "certifications" in data and isinstance(data["certifications"], list):
        data["certifications"] = _normalize_string_list(data["certifications"])
    return data


def call_llm(
    *,
    system: str,
    user_content: str = "",
    messages: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    purpose: str = "",
) -> str:
    """Make an LLM call using either Claude API or Ollama.

    If *messages* is provided, it is passed directly for multi-turn
    conversations instead of building from *user_content*.

    If model starts with 'ollama:', routes to the local Ollama instance.
    Otherwise, uses the Anthropic Claude API via call_api().
    """
    model_label = get_ollama_model_name(model) if is_ollama_model(model) else model
    if purpose:
        click.echo(f"Calling {model_label} for {purpose}...")
    if is_ollama_model(model):
        model_name = get_ollama_model_name(model)
        logger.info("Using Ollama model: %s", model_name)
        check_context_window(system, user_content)
        return _call_ollama(
            model_name=model_name,
            system=system,
            user_content=user_content,
            messages=messages,
        )
    else:
        # Use existing Claude API with retry logic
        from .api import call_api

        # Resolve "claude" shorthand to actual model ID
        api_model = CLAUDE_MODEL if model == "claude" else model
        return call_api(
            model=api_model,
            max_tokens=max_tokens,
            system=system,
            user_content=user_content,
            messages=messages,
        )
