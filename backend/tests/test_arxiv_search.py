from __future__ import annotations

import asyncio

from cli.tools.arxiv_search import search_arxiv


def test_arxiv_atom_results_are_structured(monkeypatch):
    xml = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>https://arxiv.org/abs/2601.00001</id>
        <title>  Reliable   RAG Systems </title>
        <summary> Evidence grounded generation. </summary>
        <published>2026-01-02T00:00:00Z</published>
      </entry>
    </feed>"""

    class Response:
        text = xml

        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url):
            assert "search_query=all%3Areliable" in url
            return Response()

    monkeypatch.setattr("cli.tools.arxiv_search.httpx.AsyncClient", Client)
    batch = asyncio.run(search_arxiv("reliable", max_results=3))
    assert batch.provider == "arxiv"
    assert batch.credits == 0
    assert batch.results[0].title == "Reliable RAG Systems"
    assert batch.results[0].published_at == "2026-01-02T00:00:00Z"
