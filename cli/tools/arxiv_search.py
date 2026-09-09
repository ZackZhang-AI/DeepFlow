"""Small arXiv Atom API client used by academic research steps."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import urlencode

import httpx

from cli.models import SearchBatch, SearchResult

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM = {"atom": "http://www.w3.org/2005/Atom"}


async def search_arxiv(query: str, max_results: int = 5) -> SearchBatch:
    params = urlencode(
        {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": min(max(1, max_results), 10),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    async with httpx.AsyncClient(
        timeout=15,
        headers={"User-Agent": "DeepFlow/0.1 (academic research demo)"},
    ) as client:
        response = await client.get(f"{ARXIV_API_URL}?{params}")
        response.raise_for_status()

    root = ET.fromstring(response.text)
    results: list[SearchResult] = []
    for entry in root.findall("atom:entry", ATOM):
        url = (entry.findtext("atom:id", default="", namespaces=ATOM) or "").strip()
        title = " ".join((entry.findtext("atom:title", default="", namespaces=ATOM) or "").split())
        summary = " ".join((entry.findtext("atom:summary", default="", namespaces=ATOM) or "").split())
        published = (entry.findtext("atom:published", default="", namespaces=ATOM) or "").strip()
        if url:
            results.append(
                SearchResult(
                    title=title or url,
                    url=url,
                    snippet=summary,
                    published_at=published or None,
                    source="arxiv",
                )
            )
    return SearchBatch(results=results, credits=0, provider="arxiv")
