"""Unified LLM client that wraps both Claude API and Ollama."""

import logging

import httpx

from .config import CLAUDE_MODEL, DEFAULT_MODEL, OLLAMA_BASE_URL

logger = logging.getLogger(__name__)


def is_ollama_model(model: str) -> bool:
    """Check if a model string refers to an Ollama model."""
    return model.startswith("ollama:")


def get_ollama_model_name(model: str) -> str:
    """Extract the Ollama model name from an 'ollama:name' string."""
    return model.split(":", 1)[1]


def _call_ollama(
    *,
    model_name: str,
    system: str,
    user_content: str,
    base_url: str = OLLAMA_BASE_URL,
) -> str:
    """Call the Ollama REST API and return the response text.

    Uses the /api/chat endpoint with streaming disabled.
    """
    url = f"{base_url}/api/chat"
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
    }

    logger.debug("Ollama request: model=%s, url=%s", model_name, url)
    try:
        response = httpx.post(url, json=payload, timeout=300.0)
        response.raise_for_status()
    except httpx.ConnectError as e:
        raise ConnectionError(
            f"Could not connect to Ollama at {base_url}. "
            "Is Ollama running? Start it with: ollama serve"
        ) from e
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Ollama API error: {e.response.status_code} - {e.response.text}"
        ) from e

    data = response.json()
    text = data.get("message", {}).get("content", "")
    if not text:
        raise RuntimeError(f"Empty response from Ollama model '{model_name}'")

    logger.debug("Ollama response length: %d chars", len(text))
    return text


def call_llm(
    *,
    system: str,
    user_content: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
) -> str:
    """Make an LLM call using either Claude API or Ollama.

    If model starts with 'ollama:', routes to the local Ollama instance.
    Otherwise, uses the Anthropic Claude API via call_api().
    """
    if is_ollama_model(model):
        model_name = get_ollama_model_name(model)
        logger.info("Using Ollama model: %s", model_name)
        return _call_ollama(
            model_name=model_name,
            system=system,
            user_content=user_content,
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
        )
