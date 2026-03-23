# internet_server/fetch.py

from __future__ import annotations
from typing import Dict, Any
import requests
from html.parser import HTMLParser


class FetchError(Exception):
    pass


class _TextExtractor(HTMLParser):
    """Simple HTML → text extractor using stdlib only."""
    def __init__(self) -> None:
        super().__init__()
        self.chunks = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.chunks.append(text)

    def get_text(self) -> str:
        return " ".join(self.chunks)


def fetch_page(url: str, max_chars: int = 600) -> Dict[str, Any]:
    """
    Fetch a web page and return a short, readable text preview.
    """
    r = requests.get(url, timeout=10)
    if not r.ok:
        raise FetchError(f"Fetch failed: HTTP {r.status_code}")

    content_type = r.headers.get("Content-Type", "")
    text = r.text

    # If it's HTML, extract visible text
    if "html" in content_type.lower():
        parser = _TextExtractor()
        parser.feed(text)
        text = parser.get_text()

    preview = text.strip().replace("\n", " ")
    if len(preview) > max_chars:
        preview = preview[:max_chars].rstrip() + "..."

    return {
        "url": url,
        "preview": preview,
        "content_type": content_type,
        "source": "direct-fetch",
    }
