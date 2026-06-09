"""Tests for the ``web_search`` copilot tool.

Covers the DDGS multi-engine search backend: pure-unit tests for
``_search_ddgs`` (mocked ``DDGS`` client), integration tests for the
full ``WebSearchTool._execute`` path, availability checks, and the
tool-registry wiring that keeps the SDK MCP route alive.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.copilot.model import ChatSession

from .models import ErrorResponse, WebSearchResponse, WebSearchResult
from .web_search import WebSearchTool, _search_ddgs


def _ddgs_result(**overrides: str) -> dict[str, str]:
    """Build a single DDGS result dict with sensible defaults."""
    return {
        "title": "Test Result",
        "href": "https://example.com",
        "body": "A test snippet.",
        **overrides,
    }


class TestSearchDDGS:
    """Unit tests for the DDGS multi-engine backend — mock the
    synchronous ``DDGS().text()`` call and confirm result mapping."""

    @pytest.mark.asyncio
    async def test_returns_mapped_web_search_results(self):
        raw = [
            _ddgs_result(title="Alpha", href="https://a.com", body="snippet A"),
            _ddgs_result(title="Beta", href="https://b.com", body="snippet B"),
        ]
        mock_client = MagicMock()
        mock_client.text.return_value = raw

        with patch("backend.copilot.tools.web_search.DDGS", return_value=mock_client):
            results = await _search_ddgs("test query", max_results=5)

        assert len(results) == 2
        assert results[0].title == "Alpha"
        assert results[0].url == "https://a.com"
        assert results[0].snippet == "snippet A"
        assert results[1].title == "Beta"
        assert results[1].url == "https://b.com"
        assert results[1].snippet == "snippet B"

    @pytest.mark.asyncio
    async def test_falls_back_through_backends(self):
        """First three backends fail; fourth succeeds — verify the
        caller-side log doesn't crash and we get the right result."""
        mock_client = MagicMock()
        # duckduckgo, bing, brave fail; google succeeds
        mock_client.text.side_effect = [
            RuntimeError("ddg down"),
            RuntimeError("bing down"),
            RuntimeError("brave down"),
            [_ddgs_result(title="Google win", href="https://g.com")],
        ]

        with patch("backend.copilot.tools.web_search.DDGS", return_value=mock_client):
            results = await _search_ddgs("query", max_results=5)

        assert len(results) == 1
        assert results[0].title == "Google win"
        # All 4 backends were tried
        assert mock_client.text.call_count == 4

    @pytest.mark.asyncio
    async def test_all_backends_exhausted_returns_empty(self):
        mock_client = MagicMock()
        mock_client.text.side_effect = RuntimeError("everything is down")

        with patch("backend.copilot.tools.web_search.DDGS", return_value=mock_client):
            results = await _search_ddgs("query", max_results=5)

        assert results == []
        # All backends in _DDGS_BACKENDS were tried
        assert mock_client.text.call_count == 8  # 8 backends in the chain

    @pytest.mark.asyncio
    async def test_handles_missing_fields(self):
        """DDGS entries may lack title, href, or body — map gracefully."""
        raw = [{}]
        mock_client = MagicMock()
        mock_client.text.return_value = raw

        with patch("backend.copilot.tools.web_search.DDGS", return_value=mock_client):
            results = await _search_ddgs("query", max_results=5)

        assert len(results) == 1
        assert results[0].title == ""
        assert results[0].url == ""
        assert results[0].snippet == ""

    @pytest.mark.asyncio
    async def test_uses_url_fallback_when_href_missing(self):
        raw = [_ddgs_result(href=None, url="https://alt.com")]  # type: ignore[arg-type]
        mock_client = MagicMock()
        mock_client.text.return_value = raw

        with patch("backend.copilot.tools.web_search.DDGS", return_value=mock_client):
            results = await _search_ddgs("query", max_results=5)

        assert results[0].url == "https://alt.com"


class TestWebSearchToolIsAvailable:
    """Availability depends on the configured provider."""

    def test_ddgs_always_available(self, monkeypatch):
        monkeypatch.setattr(
            "backend.copilot.tools.web_search._chat_config",
            type("C", (), {"search_provider": "ddgs"})(),
        )
        assert WebSearchTool().is_available is True

    def test_tavily_available_when_key_set(self, monkeypatch):
        monkeypatch.setattr(
            "backend.copilot.tools.web_search._chat_config",
            type("C", (), {"search_provider": "tavily", "tavily_api_key": "sk-xxx"})(),
        )
        assert WebSearchTool().is_available is True

    def test_tavily_unavailable_when_key_missing(self, monkeypatch):
        monkeypatch.setattr(
            "backend.copilot.tools.web_search._chat_config",
            type("C", (), {"search_provider": "tavily", "tavily_api_key": None})(),
        )
        assert WebSearchTool().is_available is False

    def test_serper_available_when_key_set(self, monkeypatch):
        monkeypatch.setattr(
            "backend.copilot.tools.web_search._chat_config",
            type("C", (), {"search_provider": "serper", "serper_api_key": "sk-xxx"})(),
        )
        assert WebSearchTool().is_available is True

    def test_serper_unavailable_when_key_missing(self, monkeypatch):
        monkeypatch.setattr(
            "backend.copilot.tools.web_search._chat_config",
            type("C", (), {"search_provider": "serper", "serper_api_key": None})(),
        )
        assert WebSearchTool().is_available is False


class TestWebSearchToolExecute:
    """Integration tests: mock ``_search_ddgs`` to avoid touching the real network."""

    def _session(self) -> ChatSession:
        s = ChatSession.new("test-user", dry_run=False)
        s.session_id = "sess-1"
        return s

    @pytest.mark.asyncio
    async def test_quick_search_returns_results(self, monkeypatch):
        fake_results = [
            WebSearchResult(title="R1", url="https://a.com", snippet="body 1"),
            WebSearchResult(title="R2", url="https://b.com", snippet="body 2"),
        ]

        async def _fake_search(*args: object, **kwargs: object) -> list[WebSearchResult]:
            return fake_results

        monkeypatch.setattr(
            "backend.copilot.tools.web_search._chat_config",
            type("C", (), {"search_provider": "ddgs"})(),
        )
        monkeypatch.setattr(
            "backend.copilot.tools.web_search._search_ddgs",
            _fake_search,
        )

        tool = WebSearchTool()
        result = await tool._execute(
            user_id="u1",
            session=self._session(),
            query="test query",
            max_results=5,
            deep=False,
        )

        assert isinstance(result, WebSearchResponse)
        assert result.query == "test query"
        assert len(result.results) == 2
        assert result.results[0].title == "R1"
        assert result.results[0].url == "https://a.com"
        assert result.results[0].snippet == "body 1"

    @pytest.mark.asyncio
    async def test_deep_mode_doubles_results(self, monkeypatch):
        """``deep=True`` should request 2× ``max_results`` from the backend."""
        captured_max: list[int] = []

        async def _capture_search(
            query: str, max_results: int
        ) -> list[WebSearchResult]:
            captured_max.append(max_results)
            return [WebSearchResult(title="deep", url="https://d.com", snippet="ok")]

        monkeypatch.setattr(
            "backend.copilot.tools.web_search._chat_config",
            type("C", (), {"search_provider": "ddgs"})(),
        )
        monkeypatch.setattr(
            "backend.copilot.tools.web_search._search_ddgs",
            _capture_search,
        )

        tool = WebSearchTool()
        result = await tool._execute(
            user_id="u1",
            session=self._session(),
            query="research question",
            max_results=5,
            deep=True,
        )

        assert isinstance(result, WebSearchResponse)
        assert captured_max[0] == 10  # 5 * 2

    @pytest.mark.asyncio
    async def test_no_results_returns_empty_response(self, monkeypatch):
        async def _empty(*args: object, **kwargs: object) -> list[WebSearchResult]:
            return []

        monkeypatch.setattr(
            "backend.copilot.tools.web_search._chat_config",
            type("C", (), {"search_provider": "ddgs"})(),
        )
        monkeypatch.setattr(
            "backend.copilot.tools.web_search._search_ddgs",
            _empty,
        )

        tool = WebSearchTool()
        result = await tool._execute(
            user_id="u1",
            session=self._session(),
            query="nothing matches this",
        )

        assert isinstance(result, WebSearchResponse)
        assert result.results == []
        assert result.search_requests == 0

    @pytest.mark.asyncio
    async def test_empty_query_rejected(self, monkeypatch):
        monkeypatch.setattr(
            "backend.copilot.tools.web_search._chat_config",
            type("C", (), {"search_provider": "ddgs"})(),
        )

        tool = WebSearchTool()
        result = await tool._execute(
            user_id="u1", session=self._session(), query="   "
        )

        assert isinstance(result, ErrorResponse)
        assert result.error == "missing_query"

    @pytest.mark.asyncio
    async def test_search_failure_returns_error(self, monkeypatch):
        async def _fail(*args: object, **kwargs: object) -> list[WebSearchResult]:
            raise RuntimeError("all engines down")

        monkeypatch.setattr(
            "backend.copilot.tools.web_search._chat_config",
            type("C", (), {"search_provider": "ddgs"})(),
        )
        monkeypatch.setattr(
            "backend.copilot.tools.web_search._search_ddgs",
            _fail,
        )

        tool = WebSearchTool()
        result = await tool._execute(
            user_id="u1",
            session=self._session(),
            query="anything",
        )

        assert isinstance(result, ErrorResponse)
        assert result.error == "web_search_failed"


class TestToolRegistryIntegration:
    """The tool must be registered under the ``web_search`` name so the
    SDK path dispatches to ``mcp__copilot__web_search``."""

    def test_web_search_is_in_tool_registry(self):
        from backend.copilot.tools import TOOL_REGISTRY

        assert "web_search" in TOOL_REGISTRY
        assert isinstance(TOOL_REGISTRY["web_search"], WebSearchTool)

    def test_sdk_native_websearch_is_disallowed(self):
        from backend.copilot.sdk.tool_adapter import SDK_DISALLOWED_TOOLS

        assert "WebSearch" in SDK_DISALLOWED_TOOLS
