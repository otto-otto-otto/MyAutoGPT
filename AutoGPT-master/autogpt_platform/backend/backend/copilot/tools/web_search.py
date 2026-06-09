"""Web search tool — DDGS multi-engine search (free, no API key needed).

Default backend: DDGS — 8-engine fallback chain covering DuckDuckGo,
Bing, Brave, Google, Mojeek, Yahoo, Yandex, and Wikipedia.  Runs the
synchronous DDGS client in a thread to stay async-native and avoid
blocking the copilot event loop.

Optional paid providers (Tavily, Serper) can be enabled by setting
``search_provider`` in :class:`ChatConfig` — the tool dispatches to
the matching backend.  DDGS is the default and always-available
fallback regardless of configuration.
"""

import asyncio
import logging
from typing import Any

from ddgs import DDGS

from backend.copilot.config import ChatConfig

from .base import BaseTool
from .models import ErrorResponse, ToolResponseBase, WebSearchResponse, WebSearchResult

logger = logging.getLogger(__name__)

_chat_config = ChatConfig()

_DEFAULT_MAX_RESULTS = 5
_HARD_MAX_RESULTS = 20

# Multi-engine fallback chain — mirrors the Forge WebSearchComponent order.
# Toughest → most permissive so transient upstream failures don't kill the
# whole search before a reliable backend has a chance to respond.
_DDGS_BACKENDS = [
    "duckduckgo",
    "bing",
    "brave",
    "google",
    "mojeek",
    "yahoo",
    "yandex",
    "wikipedia",
]


class WebSearchTool(BaseTool):
    """Search the public web and return cited results.

    Backend is selected via ``ChatConfig.search_provider``:
    ``"ddgs"`` (default) — free multi-engine search, always available.
    ``"tavily"`` / ``"serper"`` — paid providers, require API keys.
    """

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web for live info (news, recent docs). Returns "
            "{title, url, snippet} citations from real search results. "
            "Set deep=true when the user asks for research / comparison "
            "/ in-depth analysis — searches twice as many results across "
            "more engines. Leave deep=false for quick fact lookups. "
            "Prefer one targeted query over many reformulations."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query.",
                },
                "max_results": {
                    "type": "integer",
                    "description": (
                        f"Max results (default {_DEFAULT_MAX_RESULTS}, "
                        f"cap {_HARD_MAX_RESULTS})."
                    ),
                    "default": _DEFAULT_MAX_RESULTS,
                },
                "deep": {
                    "type": "boolean",
                    "description": (
                        "Set true only when the user explicitly asks for "
                        "deep research, comparison, or in-depth analysis. "
                        "Searches 2× results across more engines. "
                        "Default false — use for ordinary fact lookups."
                    ),
                    "default": False,
                },
            },
            "required": ["query"],
        }

    @property
    def requires_auth(self) -> bool:
        return False

    @property
    def is_available(self) -> bool:
        # DDGS is always available (free, zero-config).
        # Other providers check for API keys.
        provider = _chat_config.search_provider
        if provider == "tavily":
            return bool(_chat_config.tavily_api_key)
        if provider == "serper":
            return bool(_chat_config.serper_api_key)
        return True  # ddgs (default)

    async def _execute(
        self,
        user_id: str | None,
        session: "ChatSession",  # noqa: F821
        query: str = "",
        max_results: int = _DEFAULT_MAX_RESULTS,
        deep: bool = False,
        **kwargs: Any,
    ) -> ToolResponseBase:
        query = (query or "").strip()
        session_id = session.session_id if session else None
        if not query:
            return ErrorResponse(
                message="Please provide a non-empty search query.",
                error="missing_query",
                session_id=session_id,
            )

        try:
            max_results = int(max_results)
        except (TypeError, ValueError):
            max_results = _DEFAULT_MAX_RESULTS
        max_results = max(1, min(max_results, _HARD_MAX_RESULTS))

        # Deep mode: double the result count for broader research coverage.
        if deep:
            max_results = min(max_results * 2, _HARD_MAX_RESULTS)

        provider = _chat_config.search_provider
        try:
            results = await _search_web(query, max_results, provider=provider)
        except Exception as exc:
            logger.warning(
                "[web_search] Search failed (provider=%s) for query=%r: %s",
                provider,
                query,
                exc,
            )
            return ErrorResponse(
                message=f"Web search failed: {exc}",
                error="web_search_failed",
                session_id=session_id,
            )

        if not results:
            return WebSearchResponse(
                message=f"No results found for {query!r}.",
                query=query,
                answer="",
                results=[],
                search_requests=0,
                session_id=session_id,
            )

        return WebSearchResponse(
            message=f"Found {len(results)} result(s) for {query!r}.",
            query=query,
            answer="",
            results=results,
            search_requests=1 if results else 0,
            session_id=session_id,
        )


async def _search_web(
    query: str,
    max_results: int,
    *,
    provider: str = "ddgs",
) -> list[WebSearchResult]:
    """Dispatch to the configured search provider.

    DDGS is the default; runs synchronously in a worker thread via
    ``asyncio.to_thread`` to keep the copilot event loop free.
    """
    if provider == "tavily":
        raise NotImplementedError(
            "Tavily provider is not yet implemented. Set search_provider='ddgs' "
            "or configure a different provider."
        )
    if provider == "serper":
        raise NotImplementedError(
            "Serper provider is not yet implemented. Set search_provider='ddgs' "
            "or configure a different provider."
        )
    return await _search_ddgs(query, max_results)


async def _search_ddgs(query: str, max_results: int) -> list[WebSearchResult]:
    """Search using DDGS multi-engine search.

    Tries each backend in ``_DDGS_BACKENDS`` order until one returns
    non-empty results.  The synchronous ``DDGS.text()`` call runs in
    a worker thread to avoid blocking the event loop.
    """
    last_error: Exception | None = None
    client = DDGS()

    for backend in _DDGS_BACKENDS:
        try:
            logger.debug("[web_search] Trying DDGS backend: %s", backend)
            raw_results = await asyncio.to_thread(
                client.text,
                query,
                max_results=max_results,
                backend=backend,
                region="us-en",
                safesearch="moderate",
            )

            if raw_results:
                results = [
                    WebSearchResult(
                        title=r.get("title", ""),
                        url=r.get("href", r.get("url", "")),
                        snippet=r.get("body", r.get("description", "")),
                    )
                    for r in raw_results
                ]
                logger.info(
                    "[web_search] DDGS succeeded with %s: %d results",
                    backend,
                    len(results),
                )
                return results

        except Exception as e:
            last_error = e
            logger.warning("[web_search] DDGS %s failed: %s", backend, e)
            continue

    if last_error:
        logger.error(
            "[web_search] All DDGS backends exhausted. Last error: %s", last_error
        )

    return []
