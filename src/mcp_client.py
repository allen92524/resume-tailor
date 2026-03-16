"""MCP client wrapper for fetching web content and searching the web.

Uses Model Context Protocol (MCP) servers:
- mcp-server-fetch: fetches web pages and converts HTML to markdown
- brave-search: web search via Brave Search API (optional, needs BRAVE_API_KEY)
"""

import asyncio
import logging
import os
import shutil

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


def _find_command(name: str) -> str | None:
    """Find an executable command, checking uvx, npx, and direct paths."""
    # Check if uvx is available (preferred for Python MCP servers)
    if shutil.which("uvx"):
        return "uvx"
    # Fall back to checking if the package is installed directly
    if shutil.which(name):
        return name
    return None


async def _fetch_url_async(url: str, max_length: int = 50000) -> str:
    """Fetch a URL using the MCP fetch server and return markdown content."""
    cmd = _find_command("mcp-server-fetch")
    if not cmd:
        raise RuntimeError(
            "MCP fetch server not available. Install with: pip install mcp-server-fetch"
        )

    if cmd == "uvx":
        args = ["mcp-server-fetch"]
    else:
        args = []

    server_params = StdioServerParameters(
        command=cmd,
        args=args,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "fetch",
                arguments={
                    "url": url,
                    "max_length": max_length,
                    "raw": False,
                },
            )

            texts = []
            for content in result.content:
                if hasattr(content, "text"):
                    texts.append(content.text)

            return "\n".join(texts)


async def _search_web_async(query: str, count: int = 5) -> str:
    """Search the web using the Brave Search MCP server.

    Requires BRAVE_API_KEY environment variable.
    Returns search results as text.
    """
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "BRAVE_API_KEY not set. Get a free key at https://brave.com/search/api/"
        )

    # brave-search MCP server runs via npx
    if not shutil.which("npx"):
        raise RuntimeError("npx not found. Install Node.js to use web search.")

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@anthropic-ai/mcp-server-brave-search"],
        env={**os.environ, "BRAVE_API_KEY": api_key},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "brave_web_search",
                arguments={
                    "query": query,
                    "count": count,
                },
            )

            texts = []
            for content in result.content:
                if hasattr(content, "text"):
                    texts.append(content.text)

            return "\n".join(texts)


def fetch_url(url: str, max_length: int = 50000) -> str:
    """Fetch a URL and return its content as markdown.

    Synchronous wrapper around the async MCP fetch call.
    Spawns the MCP fetch server as a child process, fetches the page,
    and shuts down the server automatically.
    """
    logger.info("Fetching URL via MCP: %s", url)
    return asyncio.run(_fetch_url_async(url, max_length))


def search_web(query: str, count: int = 5) -> str:
    """Search the web and return results as text.

    Synchronous wrapper around the async MCP Brave Search call.
    Requires BRAVE_API_KEY environment variable.
    """
    logger.info("Web search via MCP: %s", query)
    return asyncio.run(_search_web_async(query, count))


def is_url(text: str) -> bool:
    """Check if a string looks like a URL."""
    text = text.strip()
    return text.startswith(("http://", "https://", "www."))
