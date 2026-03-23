# internet_server/news.py

from __future__ import annotations
from typing import Dict, Any, List
from duckduckgo_search import DDGS


class NewsError(Exception):
    pass


def get_news(query: str = "latest news", max_results: int = 5) -> Dict[str, Any]:
    """
    Get real news results using DuckDuckGo news search.
    Returns actual headlines with snippets and URLs.
    """
    try:
        results: List[Dict[str, Any]] = []
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results):
                results.append({
                    "title":   r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url":     r.get("url", ""),
                    "source":  r.get("source", ""),
                    "date":    r.get("date", ""),
                })

        return {
            "query":   query,
            "results": results,
            "source":  "duckduckgo.com",
        }

    except Exception as e:
        raise NewsError(f"News fetch failed: {e}")
