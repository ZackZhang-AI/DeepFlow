"""
网页抓取工具 — 使用 httpx + readability-lxml 提取正文
"""

import logging
from typing import Optional

from cli.models import CrawlResult

logger = logging.getLogger(__name__)


async def crawl_url(url: str, timeout: int = 20) -> CrawlResult:
    """
    抓取单个 URL 并提取正文。

    使用 readability-lxml 提取主要内容，如果不可用则退回纯文本提取。
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=float(timeout)) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
                follow_redirects=True,
            )
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        logger.warning(f"抓取失败 {url}: {e}")
        return CrawlResult(
            url=url,
            title="",
            content="",
            success=False,
            error=str(e),
        )

    # 提取标题
    title = _extract_title(html)

    # 提取正文
    content = _extract_content(html, url)

    return CrawlResult(
        url=url,
        title=title,
        content=content,
        raw_text_length=len(html),
        success=True,
    )


async def crawl_urls(urls: list[str], max_concurrent: int = 5) -> list[CrawlResult]:
    """并行抓取多个 URL"""
    import asyncio

    semaphore = asyncio.Semaphore(max_concurrent)

    async def crawl_with_limit(url: str) -> CrawlResult:
        async with semaphore:
            return await crawl_url(url)

    tasks = [crawl_with_limit(u) for u in urls]
    return await asyncio.gather(*tasks, return_exceptions=False)


def _extract_title(html: str) -> str:
    """从 HTML 中提取标题"""
    import re

    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1).strip()
        # 清理 HTML 实体
        title = title.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        title = title.replace("&quot;", '"').replace("&#39;", "'")
        return title[:200]  # 限制长度
    return ""


def _extract_content(html: str, url: str) -> str:
    """从 HTML 中提取正文内容（Markdown 格式）"""
    try:
        from readability import Document

        doc = Document(html)
        title = doc.title()
        summary_html = doc.summary()

        # 将 HTML 转为纯文本/Markdown
        text = _html_to_text(summary_html)
        return f"# {title}\n\n{text}"
    except ImportError:
        # 降级：简单的纯文本提取
        return _fallback_extract(html)


def _html_to_text(html: str) -> str:
    """将 HTML 转为适合 LLM 阅读的文本"""
    import re

    # 移除 script 和 style
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # 替换常见标签
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</p>", "\n\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</h[1-6]>", "\n\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</li>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</tr>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</td>", " | ", html, flags=re.IGNORECASE)

    # 移除所有标签
    html = re.sub(r"<[^>]+>", "", html)

    # 解码实体
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    html = html.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")

    # 清理多余空行
    html = re.sub(r"\n\s*\n\s*\n+", "\n\n", html)
    html = html.strip()

    # 限制长度
    if len(html) > 8000:
        html = html[:8000] + "\n\n... (内容已截断)"

    return html


def _fallback_extract(html: str) -> str:
    """纯文本降级提取"""
    return _html_to_text(html)
