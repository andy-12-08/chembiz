"""Smoke test for web_search_tool."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import dotenv_values, load_dotenv  # noqa: E402

from backend.tools.tools import web_search_tool  # noqa: E402

_DOCKER_ENV = _REPO_ROOT / "docker" / ".env"
_ROOT_ENV = _REPO_ROOT / ".env"

load_dotenv(_DOCKER_ENV)
if _ROOT_ENV.is_file():
    for key, value in dotenv_values(_ROOT_ENV).items():
        if value is None:
            continue
        os.environ[key] = str(value)

SESSION_ID = "web-search-test-session"
QUERY = "Latest best practices for retrieval augmented generation in production"


async def main() -> None:
    """Run a live Tavily web-search smoke test and print normalized results.

    Returns:
        None.
    """
    if not os.environ.get("TAVILY_API_KEY", "").strip():
        print("TAVILY_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    results = await web_search_tool.ainvoke(
        {
            "session_id": SESSION_ID,
            "query": QUERY,
        }
    )

    print(f"tool: {web_search_tool.name}")
    print(f"session_id: {SESSION_ID}")
    print(f"query: {QUERY}")
    print(f"results: {len(results)}")

    for i, row in enumerate(results, 1):
        title = str(row.get("title") or "")
        url = str(row.get("url") or "")
        score = row.get("score")
        snippet = str(row.get("snippet") or "")
        content = str(row.get("content") or "")
        print(f"--- result {i} score={score} ---")
        print(f"title: {title}")
        print(f"url: {url}")
        print(f"snippet: {snippet[:240]}")
        print(f"content: {content[:360]}")

    if not results:
        print("FAIL: no web results returned.", file=sys.stderr)
        sys.exit(1)

    print("PASS: web_search_tool completed.")


if __name__ == "__main__":
    asyncio.run(main())
