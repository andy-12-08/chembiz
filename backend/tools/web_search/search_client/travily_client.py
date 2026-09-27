from __future__ import annotations

import asyncio
import logging
import os
from urllib.parse import urlparse

from tavily import AsyncTavilyClient

from backend.config import (
    TAVILY_SEARCH_DEPTH,
    WEB_SEARCH_CONTENT_MAX_CHARS,
    WEB_SEARCH_DOMAIN_FILTER_MODE,
    WEB_SEARCH_DOMAINS,
    WEB_SEARCH_MAX_RESULTS,
    WEB_SEARCH_TIMEOUT_SECONDS,
)
from backend.models.pydantic_models import WebSearchResult

logger = logging.getLogger(__name__)


class TravilyWebSearchClient:
    """Tavily adapter that normalizes web search output for tool use."""

    def __init__(
        self,
        *,
        search_depth: str = TAVILY_SEARCH_DEPTH,
        max_results: int = WEB_SEARCH_MAX_RESULTS,
        domain_filter_mode: str = WEB_SEARCH_DOMAIN_FILTER_MODE,
        domains: list[str] = WEB_SEARCH_DOMAINS,
        max_content_chars: int = WEB_SEARCH_CONTENT_MAX_CHARS,
        timeout_seconds: int = WEB_SEARCH_TIMEOUT_SECONDS,
    ) -> None:
        """Bind Tavily client and config defaults.

        Args:
            search_depth: Tavily search depth value.
            max_results: Max number of results from provider.
            domain_filter_mode: off, include, or exclude.
            domains: Domain list used by include or exclude modes.
            max_content_chars: Max characters kept in content per result.
            timeout_seconds: Timeout for provider call.
        """
        api_key = os.environ["TAVILY_API_KEY"]
        self._client = AsyncTavilyClient(api_key=api_key)
        self._search_depth = search_depth
        self._max_results = max_results
        self._domain_filter_mode = domain_filter_mode
        self._domains = domains
        self._max_content_chars = max_content_chars
        self._timeout_seconds = timeout_seconds

    def _domain_filters(self) -> tuple[list[str] | None, list[str] | None]:
        """Resolve configured domains into provider include or exclude filters.

        Returns:
            Include-domain and exclude-domain lists; an unused filter is None.

        Raises:
            ValueError: The configured domain-filter mode is unsupported.
        """
        mode = self._domain_filter_mode.strip().lower()
        if not self._domains or mode == "off":
            return None, None
        if mode == "include":
            include_domains = list(self._domains)
            exclude_domains = None
            return include_domains, exclude_domains
        if mode == "exclude":
            include_domains = None
            exclude_domains = list(self._domains)
            return include_domains, exclude_domains
        raise ValueError(
            f"WEB_SEARCH_DOMAIN_FILTER_MODE must be off, include, or exclude, got {self._domain_filter_mode}"
        )

    async def search(self, session_id: str, query: str) -> list[WebSearchResult]:
        """Search Tavily and return normalized results.

        Args:
            session_id: Session id for log correlation.
            query: Natural language web query.

        Returns:
            Normalized web search results.
        """
        include_domains, exclude_domains = self._domain_filters()
        logger.info(
            f"Session ID: {session_id}; web_search start provider=tavily "
            f"query={query} max_results={self._max_results} depth={self._search_depth}"
        )

        raw = await asyncio.wait_for(
            self._client.search(
                query=query,
                search_depth=self._search_depth,
                max_results=self._max_results,
                include_raw_content=True,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
            ),
            timeout=self._timeout_seconds,
        )

        results: list[WebSearchResult] = []
        for item in raw.get("results", []):
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            domain = urlparse(url).netloc
            snippet = (item.get("content") or "").strip()
            content = (item.get("raw_content") or snippet).strip()
            if len(content) > self._max_content_chars:
                content = content[: self._max_content_chars]

            results.append(
                WebSearchResult(
                    title=(item.get("title") or "").strip(),
                    url=url,
                    snippet=snippet,
                    content=content,
                    source_domain=domain,
                    published_at=item.get("published_date"),
                    score=item.get("score"),
                    query=query,
                )
            )
        logger.info(
            f"Session ID: {session_id}; web_search ok provider=tavily results={len(results)}"
        )
        return results
