"""
搜索工具 — Tavily (主) + SerpAPI (备用)
"""

import logging
from typing import Optional

from cli.config import Config
from cli.models import SearchResult

logger = logging.getLogger(__name__)


async def web_search(
    query: str,
    max_results: int = 8,
    include_raw_content: bool = False,
) -> list[SearchResult]:
    """
    执行一次搜索，自动降级。

    主搜索源: Tavily
    备用搜索源: SerpAPI
    """
    if Config.TAVILY_API_KEY:
        try:
            return await _tavily_search(query, max_results, include_raw_content)
        except Exception as e:
            logger.warning(f"Tavily 搜索失败: {e}，尝试降级到 SerpAPI")

    if Config.SERPAPI_API_KEY:
        try:
            return await _serpapi_search(query, max_results)
        except Exception as e:
            logger.error(f"SerpAPI 搜索也失败: {e}")

    logger.error(f"所有搜索源不可用，query='{query}'")
    return []


async def web_search_multi(
    queries: list[str],
    max_results_per_query: int = 5,
) -> list[SearchResult]:
    """
    对多个搜索词并行搜索，去重合并结果。
    """
    import asyncio

    tasks = [web_search(q, max_results=max_results_per_query) for q in queries]
    results_per_query = await asyncio.gather(*tasks, return_exceptions=True)

    seen_urls: set[str] = set()
    merged: list[SearchResult] = []

    for results in results_per_query:
        if isinstance(results, Exception):
            continue
        for r in results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                merged.append(r)

    return merged


async def _tavily_search(
    query: str,
    max_results: int = 8,
    include_raw_content: bool = False,
) -> list[SearchResult]:
    """
    Tavily Search API
    https://docs.tavily.com/docs/api-reference/endpoint/search
    """
    from tavily import TavilyClient

    client = TavilyClient(api_key=Config.TAVILY_API_KEY)
    response = client.search(
        query=query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        search_depth="advanced",
    )

    results: list[SearchResult] = []
    for item in response.get("results", []):
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", item.get("snippet", "")),
                published_at=item.get("published_date"),
                source="tavily",
            )
        )
    return results


async def _serpapi_search(
    query: str,
    max_results: int = 8,
) -> list[SearchResult]:
    """
    SerpAPI 搜索 (备用)，使用 Google 引擎。
    """
    import httpx

    params = {
        "api_key": Config.SERPAPI_API_KEY,
        "q": query,
        "num": min(max_results, 10),
        "engine": "google",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get("https://serpapi.com/search", params=params)
        resp.raise_for_status()
        data = resp.json()

    results: list[SearchResult] = []
    for item in data.get("organic_results", [])[:max_results]:
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                published_at=item.get("date"),
                source="serpapi",
            )
        )
    return results
