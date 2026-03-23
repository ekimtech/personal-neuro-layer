# internet_server/search.py

from __future__ import annotations
from typing import Dict, Any, List
from duckduckgo_search import DDGS


class SearchError(Exception):
    pass


def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Perform a real web search using the duckduckgo_search library.
    Returns actual search results, not just instant answers.
    """
    try:
        results: List[Dict[str, Any]] = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title":   r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url":     r.get("href", ""),
                })

        return {
            "query":   query,
            "results": results,
            "source":  "duckduckgo.com",
        }

    except Exception as e:
        raise SearchError(f"Web search failed: {e}")
