"""
工具函数入口
"""

from .web_search import web_search, web_search_multi
from .web_crawl import crawl_url, crawl_urls

__all__ = ["web_search", "web_search_multi", "crawl_url", "crawl_urls"]
