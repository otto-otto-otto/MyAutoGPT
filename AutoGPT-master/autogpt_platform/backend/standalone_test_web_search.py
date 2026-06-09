"""Standalone test for web_search module — bypasses the full __init__.py
import chain so we can test without all backend infrastructure."""

import asyncio
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

# ---- fake prisma and friends so imports in config.py et al don't blow up ----
_prisma = ModuleType("prisma")
_prisma.models = ModuleType("prisma.models")
for _k in ("AgentBlock", "ChatMessage", "AgentGraph", "AgentNode", "AgentNodeLink",
           "AgentGraphExecution", "AgentNodeExecution", "AgentGraphExecutionSchedule",
           "User", "Organization", "Profile", "Credentials", "CredentialsMeta",
           "LibraryAgent", "AgentTrigger", "MarketplaceAgent", "AgentStoreListing",
           "Folder", "FolderAgent", "APIKey", "CreditTransaction", "Notification",
           "Webhook", "Integration", "FeatureFlag"):
    setattr(_prisma.models, _k, type(_k, (), {}))
sys.modules["prisma"] = _prisma
sys.modules["prisma.models"] = _prisma.models

_sdk = ModuleType("prisma._generator")  # prisma.gen depends on this
sys.modules["prisma._generator"] = _sdk

# Stub any module we know the import chain touches
for _mod in (
    "autogpt_libs", "autogpt_libs.auth", "autogpt_libs.auth.dependencies",
    "autogpt_libs.logging", "autogpt_libs.logging.config",
    "autogpt_libs.supabase_client", "autogpt_libs.supabase_client.client",
    "backend.util.workspace", "backend.copilot.rate_limit",
    "launchdarkly_server_sdk",
):
    sys.modules[_mod] = ModuleType(_mod)

# ---- mock the ddgs import and ChatConfig ----
import backend.copilot.config as config_mod

# ---- now reload our web_search module in isolation ----
import importlib
import backend.copilot.tools.web_search as ws_mod
importlib.reload(ws_mod)

from backend.copilot.tools.web_search import WebSearchTool, _search_ddgs
from backend.copilot.tools.models import WebSearchResult, WebSearchResponse, ErrorResponse

# ===== tests =====

def test_ddgs_basic():
    """Verify _search_ddgs maps DDGS results correctly."""
    raw = [
        {"title": "Alpha", "href": "https://a.com", "body": "snippet A"},
        {"title": "Beta", "href": "https://b.com", "body": "snippet B"},
    ]
    mock_client = MagicMock()
    mock_client.text.return_value = raw

    with patch("backend.copilot.tools.web_search.DDGS", return_value=mock_client):
        results = asyncio.run(_search_ddgs("test query", max_results=5))

    assert len(results) == 2
    assert results[0].title == "Alpha"
    assert results[0].url == "https://a.com"
    assert results[0].snippet == "snippet A"
    assert results[1].title == "Beta"
    print("  PASS test_ddgs_basic")


def test_ddgs_fallback_chain():
    """Verify fallback: first 3 backends fail, 4th succeeds."""
    mock_client = MagicMock()
    mock_client.text.side_effect = [
        RuntimeError("ddg down"),
        RuntimeError("bing down"),
        RuntimeError("brave down"),
        [{"title": "Google win", "href": "https://g.com", "body": "ok"}],
    ]

    with patch("backend.copilot.tools.web_search.DDGS", return_value=mock_client):
        results = asyncio.run(_search_ddgs("query", max_results=5))

    assert len(results) == 1
    assert results[0].title == "Google win"
    assert mock_client.text.call_count == 4
    print("  PASS test_ddgs_fallback_chain")


def test_ddgs_all_exhausted():
    """Verify empty result when all backends fail."""
    mock_client = MagicMock()
    mock_client.text.side_effect = RuntimeError("everything down")

    with patch("backend.copilot.tools.web_search.DDGS", return_value=mock_client):
        results = asyncio.run(_search_ddgs("query", max_results=5))

    assert results == []
    assert mock_client.text.call_count == 8  # all _DDGS_BACKENDS
    print("  PASS test_ddgs_all_exhausted")


def test_ddgs_missing_fields():
    """Missing fields map to empty strings gracefully."""
    mock_client = MagicMock()
    mock_client.text.return_value = [{}]

    with patch("backend.copilot.tools.web_search.DDGS", return_value=mock_client):
        results = asyncio.run(_search_ddgs("query", max_results=5))

    assert len(results) == 1
    assert results[0].title == ""
    assert results[0].url == ""
    assert results[0].snippet == ""
    print("  PASS test_ddgs_missing_fields")


def test_ddgs_url_fallback():
    """href missing -> falls back to url field."""
    mock_client = MagicMock()
    mock_client.text.return_value = [{"title": "t", "url": "https://alt.com", "body": "b"}]

    with patch("backend.copilot.tools.web_search.DDGS", return_value=mock_client):
        results = asyncio.run(_search_ddgs("query", max_results=5))

    assert results[0].url == "https://alt.com"
    print("  PASS test_ddgs_url_fallback")


def test_is_available_default():
    """DDGS provider is always available."""
    tool = WebSearchTool()
    # With default ChatConfig (search_provider="ddgs"), is_available should be True
    result = tool.is_available
    print(f"  is_available with DDGS: {result}")
    assert result is True
    print("  PASS test_is_available_default")


def test_tool_execute_integration():
    """Integration: _execute uses _search_ddgs and returns WebSearchResponse."""
    fake_results = [
        WebSearchResult(title="R1", url="https://a.com", snippet="body 1"),
    ]

    from backend.copilot.model import ChatSession
    session = ChatSession.new("test-user", dry_run=False)
    session.session_id = "sess-1"

    original_search = ws_mod._search_ddgs

    async def _fake(*a, **kw):
        return fake_results
    ws_mod._search_ddgs = _fake  # type: ignore[assignment]

    try:
        tool = WebSearchTool()
        result = asyncio.run(tool._execute(
            user_id="u1",
            session=session,
            query="test",
            max_results=5,
            deep=False,
        ))

        assert isinstance(result, WebSearchResponse)
        assert result.query == "test"
        assert len(result.results) == 1
        assert result.results[0].title == "R1"
        print("  PASS test_tool_execute_integration")
    finally:
        ws_mod._search_ddgs = original_search


def test_empty_query_rejected():
    """Empty/whitespace query returns ErrorResponse."""
    from backend.copilot.model import ChatSession
    session = ChatSession.new("test-user", dry_run=False)
    session.session_id = "sess-1"

    tool = WebSearchTool()
    result = asyncio.run(tool._execute(
        user_id="u1", session=session, query="   ",
    ))
    assert isinstance(result, ErrorResponse)
    assert result.error == "missing_query"
    print("  PASS test_empty_query_rejected")


def test_no_results_response():
    """No results from DDGS returns empty WebSearchResponse."""
    from backend.copilot.model import ChatSession
    session = ChatSession.new("test-user", dry_run=False)
    session.session_id = "sess-1"

    original_search = ws_mod._search_ddgs

    async def _empty(*a, **kw):
        return []
    ws_mod._search_ddgs = _empty  # type: ignore[assignment]

    try:
        tool = WebSearchTool()
        result = asyncio.run(tool._execute(
            user_id="u1", session=session, query="nothing",
        ))
        assert isinstance(result, WebSearchResponse)
        assert result.results == []
        assert result.search_requests == 0
        print("  PASS test_no_results_response")
    finally:
        ws_mod._search_ddgs = original_search


def test_deep_mode_doubles_results():
    """deep=True doubles max_results passed to DDGS."""
    captured = []

    async def _capture(query: str, max_results: int):
        captured.append(max_results)
        return [WebSearchResult(title="d", url="https://d.com", snippet="ok")]

    from backend.copilot.model import ChatSession
    session = ChatSession.new("test-user", dry_run=False)
    session.session_id = "sess-1"

    original_search = ws_mod._search_ddgs
    ws_mod._search_ddgs = _capture  # type: ignore[assignment]

    try:
        tool = WebSearchTool()
        asyncio.run(tool._execute(
            user_id="u1", session=session, query="research",
            max_results=5, deep=True,
        ))
        assert captured[0] == 10  # 5 * 2
        print("  PASS test_deep_mode_doubles_results")
    finally:
        ws_mod._search_ddgs = original_search


if __name__ == "__main__":
    print("Running standalone web_search tests...\n")
    tests = [
        test_ddgs_basic,
        test_ddgs_fallback_chain,
        test_ddgs_all_exhausted,
        test_ddgs_missing_fields,
        test_ddgs_url_fallback,
        test_is_available_default,
        test_tool_execute_integration,
        test_empty_query_rejected,
        test_no_results_response,
        test_deep_mode_doubles_results,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  FAIL {t.__name__}: {e}")

    print(f"\n{passed}/{len(tests)} tests passed")
    sys.exit(0 if passed == len(tests) else 1)
