"""Baidu Search Block — Chinese web search via page scraping + BeautifulSoup.

Uses aiohttp for async HTTP requests and BeautifulSoup for robust HTML
parsing (instead of fragile regex).  Includes User-Agent rotation, retries,
multi-pattern fallback to handle Baidu's varying page structures, and
optional full-page content extraction for each result.
"""

import asyncio
import logging
import random
import re
from typing import Any, Literal
from urllib.parse import quote

import aiohttp
from bs4 import BeautifulSoup

from backend.blocks._base import (
    Block,
    BlockCategory,
    BlockOutput,
    BlockSchemaInput,
    BlockSchemaOutput,
)
from backend.blocks.chinese_search._anti_bot import pick_bot_headers
from backend.data.model import SchemaField
from backend.util.cache import get_chinese_search_cache, set_chinese_search_cache

logger = logging.getLogger(__name__)

# Max concurrent page fetches to avoid overwhelming target servers
_MAX_CONCURRENT_FETCHES = 3
# Max characters to extract per page
_MAX_CONTENT_CHARS = 8000
# Cache TTL for search results (seconds) — 5 minutes
_SEARCH_CACHE_TTL = 300
# Rate limiter: 1 concurrent search call + random jitter
_SEARCH_SEMAPHORE = asyncio.Semaphore(1)


class BaiduSearchBlock(Block):
    """Search the Chinese web using Baidu.

    Enhanced implementation using BeautifulSoup for robust HTML parsing,
    User-Agent rotation, retries, multi-pattern fallback extraction, and
    optional full-page content fetching for each search result.
    """

    class Input(BlockSchemaInput):
        query: str = SchemaField(
            description="Chinese search query string",
            placeholder="请输入搜索关键词",
        )
        search_type: Literal["web", "news", "baike"] = SchemaField(
            default="web",
            description="Search type: web, news, or baike (encyclopedia)",
        )
        max_results: int = SchemaField(
            default=10,
            ge=1,
            le=50,
            description="Maximum number of results to return",
        )
        fetch_content: bool = SchemaField(
            default=True,
            description="Whether to fetch and extract the full page content for each result URL",
        )

    class Output(BlockSchemaOutput):
        results: list[dict[str, Any]] = SchemaField(
            description="List of results with title, url, snippet, content, and relevance"
        )
        total_count: int = SchemaField(description="Total number of results found")
        error: str = SchemaField(description="Error message if the search fails")

    def __init__(self):
        super().__init__(
            id="a1b2c3d4-0001-4000-8000-000000000001",
            description="搜索百度网页/新闻/百科，返回标题、摘要、链接及页面全文内容",
            categories={BlockCategory.SEARCH},
            input_schema=BaiduSearchBlock.Input,
            output_schema=BaiduSearchBlock.Output,
            test_input={"query": "人工智能"},
            test_output=[
                ("results", [{"title": "测试结果", "url": "https://example.com", "snippet": "测试摘要", "content": "页面正文内容..."}]),
                ("total_count", 1),
            ],
            test_mock={
                "_do_search": lambda query, search_type, max_results: (
                    [{"title": "测试结果", "url": "https://example.com", "snippet": "测试摘要", "engine": "baidu"}],
                    1,
                ),
                "_fetch_page_content": lambda url: "页面正文内容...",
            },
        )
        # Persistent cookie jar so search + detail fetches share session
        # state across retries (reduces captcha probability).
        self._cookie_jar = aiohttp.CookieJar()

    async def run(self, input_data: Input, **kwargs) -> BlockOutput:
        query = input_data.query.strip()
        if not query:
            yield "error", "搜索关键词不能为空"
            return

        try:
            results, total = await self._do_search(
                query=query,
                search_type=input_data.search_type,
                max_results=input_data.max_results,
            )

            # Optionally fetch full page content for each result URL
            if input_data.fetch_content and results:
                results = await self._enrich_with_content(results)

            yield "results", results
            yield "total_count", total
        except Exception as e:
            logger.exception("Baidu search failed for query=%r", query)
            yield "error", f"百度搜索失败: {e}"

    async def _do_search(
        self,
        query: str,
        search_type: str,
        max_results: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Fetch and parse Baidu search results with retry + cache + rate limit."""
        # 1. Check semantic cache (5 min TTL)
        cached = await get_chinese_search_cache(query, engine="baidu")
        if cached is not None:
            logger.debug("Baidu search cache hit for %r", query)
            return cached[:max_results], len(cached)

        # 2. Rate-limit: at most 1 concurrent search to baidu.com
        async with _SEARCH_SEMAPHORE:
            # Small random jitter so bursts don't look like a bot
            await asyncio.sleep(random.uniform(0.1, 0.5))

            encoded_query = quote(query, safe="")

            urls = {
                "web": f"https://www.baidu.com/s?wd={encoded_query}&rn={max_results}",
                "news": f"https://www.baidu.com/s?wd={encoded_query}&tn=news&rtt=1",
                "baike": f"https://baike.baidu.com/item/{encoded_query}",
            }
            url = urls.get(search_type, urls["web"])

            last_error = None
            for attempt in range(3):
                try:
                    html = await self._fetch_page(url, attempt)
                    results = self._parse_results(html, search_type)
                    if results:
                        # Store in semantic cache
                        await set_chinese_search_cache(
                            query, results, engine="baidu",
                            ttl_seconds=_SEARCH_CACHE_TTL,
                        )
                        return results[:max_results], len(results)
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "Baidu search attempt %d/3 failed for %r: %s",
                        attempt + 1, query, e,
                    )
                    if attempt < 2:
                        await asyncio.sleep((attempt + 1) * 1.5)

            raise last_error or RuntimeError("Baidu search returned no results")

    async def _fetch_page(self, url: str, attempt: int) -> str:
        """Fetch a page with rotating User-Agent and extended timeout."""
        bot = pick_bot_headers()
        headers = {
            "User-Agent": bot["user_agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "Sec-Ch-Ua": bot["sec_ch_ua"],
            "Sec-Ch-Ua-Mobile": bot["sec_ch_ua_mobile"],
            "Sec-Ch-Ua-Platform": bot["sec_ch_ua_platform"],
            "Referer": "https://www.baidu.com/",
        }

        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        connector = aiohttp.TCPConnector(force_close=True)

        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=headers,
            cookie_jar=self._cookie_jar,
        ) as session:
            async with session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")
                return await response.text()

    def _parse_results(self, html: str, search_type: str) -> list[dict[str, Any]]:
        """Parse Baidu search results using BeautifulSoup with multi-pattern fallback."""
        soup = BeautifulSoup(html, "lxml")
        results: list[dict[str, Any]] = []

        if search_type == "baike":
            return self._parse_baike_results(soup)

        # Pattern 1: Modern Baidu structure (div.result with h3 > a)
        for container in soup.select("div.result, div.result-op, div.c-container"):
            result = self._extract_from_container(container)
            if result:
                results.append(result)

        # Pattern 2: Fallback — any h3 containing a link
        if not results:
            for h3 in soup.find_all("h3"):
                a = h3.find("a", href=True)
                if a and a.get_text(strip=True):
                    url = str(a["href"])
                    if not url.startswith("javascript:"):
                        results.append({
                            "title": a.get_text(strip=True),
                            "url": url,
                            "snippet": "",
                            "engine": "baidu",
                            "search_type": search_type,
                            "relevance_score": 0.7,
                        })

        # Pattern 3: Fallback — all external links with meaningful text
        if not results:
            for a in soup.find_all("a", href=True):
                title = a.get_text(strip=True)
                url = str(a["href"])
                if (
                    title
                    and len(title) >= 4
                    and url.startswith("http")
                    and "baidu.com" not in url
                ):
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": "",
                        "engine": "baidu",
                        "search_type": search_type,
                        "relevance_score": 0.5,
                    })

        return results

    def _extract_from_container(self, container) -> dict[str, Any] | None:
        """Extract title, url, snippet from a Baidu result container."""
        # Title
        title_elem = container.select_one("h3 a, .t a, a[class*='title']")
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)
        url = str(title_elem.get("href", ""))
        if not title or url.startswith("javascript:"):
            return None

        # Snippet
        snippet = ""
        snippet_elem = container.select_one(
            "span.content-right_8Zs40, .c-abstract, .c-span-last, "
            ".c-span18 span, .c-row span, p.c-line-clamp1"
        )
        if snippet_elem:
            snippet = snippet_elem.get_text(strip=True)
        if not snippet:
            # Fallback: any paragraph-like element
            for p in container.find_all(["p", "span", "div", "em"]):
                text = p.get_text(strip=True)
                if len(text) > 15 and text != title:
                    snippet = text
                    break

        return {
            "title": title,
            "url": url,
            "snippet": snippet,
            "engine": "baidu",
            "search_type": "",
            "relevance_score": 1.0,
        }

    def _parse_baike_results(self, soup) -> list[dict[str, Any]]:
        """Parse Baidu Baike (encyclopedia) page."""
        results: list[dict[str, Any]] = []
        title_elem = soup.select_one("h1, .lemmaTitleH1, .lemmaWgt-lemmaTitle-title h1")
        title = title_elem.get_text(strip=True) if title_elem else ""

        summary_elem = soup.select_one(
            "div.lemma-summary, div.para, .lemmaWgt-lemmaSummary"
        )
        snippet = summary_elem.get_text(strip=True) if summary_elem else ""

        if title:
            results.append({
                "title": title,
                "url": "",
                "snippet": snippet,
                "engine": "baidu",
                "search_type": "baike",
                "relevance_score": 1.0,
            })

        # Also collect sub-section links
        for a in soup.select(".lemmaWgt-subLemmaListTitle a, h2 a, .para-title a"):
            sub_title = a.get_text(strip=True)
            url = str(a.get("href", ""))
            if sub_title:
                results.append({
                    "title": sub_title,
                    "url": url,
                    "snippet": "",
                    "engine": "baidu",
                    "search_type": "baike",
                    "relevance_score": 0.8,
                })

        return results

    # ------------------------------------------------------------------
    # Page content extraction
    # ------------------------------------------------------------------

    async def _enrich_with_content(
        self, results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Fetch and extract page content for each result concurrently.

        Uses an asyncio semaphore to limit concurrent fetches so we don't
        overwhelm target servers.
        """
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_FETCHES)
        tasks = [self._fetch_page_content(r.get("url", ""), semaphore) for r in results]
        contents = await asyncio.gather(*tasks, return_exceptions=True)

        for result, content in zip(results, contents):
            if isinstance(content, Exception):
                logger.debug(
                    "Content fetch failed for %s: %s", result.get("url"), content
                )
                result["content"] = ""
            else:
                result["content"] = content

        return results

    async def _fetch_page_content(self, url: str, semaphore: asyncio.Semaphore) -> str:
        """Fetch a single page and extract its main text content.

        Skips invalid or empty URLs.  Uses the semaphore to throttle
        concurrent requests.
        """
        if not url or not url.startswith("http"):
            return ""

        async with semaphore:
            try:
                bot = pick_bot_headers()
                headers = {
                    "User-Agent": bot["user_agent"],
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate",
                }
                timeout = aiohttp.ClientTimeout(total=15, connect=8)
                connector = aiohttp.TCPConnector(force_close=True)

                async with aiohttp.ClientSession(
                    timeout=timeout, connector=connector
                ) as session:
                    async with session.get(
                        url, headers=headers, allow_redirects=True
                    ) as response:
                        if response.status != 200:
                            return ""
                        html = await response.text()

                return self._extract_text_from_html(html)

            except (aiohttp.ClientError, asyncio.TimeoutError, UnicodeDecodeError) as e:
                logger.debug("Failed to fetch content from %s: %s", url, e)
                return ""
            except Exception:
                return ""

    @staticmethod
    def _extract_text_from_html(html: str) -> str:
        """Extract readable text content from an HTML page.

        Strategy:
        1. Parse with BeautifulSoup (lxml for speed).
        2. Strip non-content elements (script, style, nav, footer, header...).
        3. Try known content containers (article, main, .content, etc.).
        4. Fall back to body text if no container found.
        5. Clean and truncate the result.
        """
        soup = BeautifulSoup(html, "lxml")

        # Remove non-content elements
        for tag in soup.find_all([
            "script", "style", "nav", "footer", "header",
            "noscript", "iframe", "form", "button", "input",
            "select", "textarea", "svg", "canvas",
        ]):
            tag.decompose()

        # Also remove common sidebar/ad elements
        for tag in soup.select(
            ".sidebar, .advertisement, .ad, .ads, .nav, .menu, "
            ".footer, .header, .comment, .comments, .related, "
            '[role="navigation"], [role="banner"], [role="contentinfo"]'
        ):
            tag.decompose()

        # Try to find the main content container
        content_selectors = [
            "article",
            '[role="main"]',
            "main",
            ".content",
            ".article",
            ".post",
            ".post-content",
            ".article-content",
            ".entry-content",
            "#content",
            "#article",
            "#main",
            "#main-content",
        ]
        container = None
        for selector in content_selectors:
            container = soup.select_one(selector)
            if container and len(container.get_text(strip=True)) > 200:
                break
            container = None

        if container is None:
            container = soup.body
        if container is None:
            container = soup

        # Extract text from paragraphs, headings, and list items
        text_parts: list[str] = []
        for tag in container.find_all(
            ["p", "h1", "h2", "h3", "h4", "h5", "h6",
             "li", "td", "th", "pre", "blockquote"]
        ):
            text = tag.get_text(separator=" ", strip=True)
            if text and len(text) > 10:
                text = re.sub(r"\s+", " ", text)
                if len(text.split()) >= 3:
                    text_parts.append(text)

        content = "\n".join(text_parts)

        # Fallback: extract all visible text if nothing found
        if not content and container:
            content = container.get_text(separator=" ", strip=True)
            content = re.sub(r"\s+", " ", content)

        return BaiduSearchBlock._clean_text(content)

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean extracted text: normalize whitespace and truncate."""
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        text = text.strip()

        if len(text) > _MAX_CONTENT_CHARS:
            text = text[:_MAX_CONTENT_CHARS] + "…"

        return text
