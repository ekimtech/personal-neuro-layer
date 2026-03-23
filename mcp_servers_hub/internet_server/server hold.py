print("🔥 INTERNET SERVER LOADED:", __file__)

import json
import re
import urllib.request
import urllib.parse
import urllib.error
from html.parser import HTMLParser

# ---------------------------------------------------------
# Optional BeautifulSoup support
# ---------------------------------------------------------
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# ---------------------------------------------------------
# Default RSS feeds
# ---------------------------------------------------------
DEFAULT_FEEDS = {
    "bbc_world":     "http://feeds.bbci.co.uk/news/world/rss.xml",
    "bbc_tech":      "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "reuters_world": "https://feeds.reuters.com/reuters/worldNews",
    "reuters_tech":  "https://feeds.reuters.com/reuters/technologyNews",
    "ars_technica":  "http://feeds.arstechnica.com/arstechnica/index",
    "hacker_news":   "https://news.ycombinator.com/rss",
}

# ---------------------------------------------------------
# Utility: safe HTTP fetch
# ---------------------------------------------------------
def http_get(url, timeout=10):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Jarvis/4.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")

# ---------------------------------------------------------
# Utility: strip HTML tags
# ---------------------------------------------------------
class TagStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []

    def handle_data(self, data):
        self.text_parts.append(data)

    def get_text(self):
        return " ".join(self.text_parts)

def strip_html(html):
    stripper = TagStripper()
    stripper.feed(html)
    text = stripper.get_text()
    text = re.sub(r"\s+", " ", text).strip()
    return text

# ---------------------------------------------------------
# Web search (DuckDuckGo)
# ---------------------------------------------------------
def run_web_search(payload: dict):
    query = payload.get("query", "")
    max_results = payload.get("max_results", 5)

    try:
        params = urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1"
        })
        url = f"https://api.duckduckgo.com/?{params}"
        raw = http_get(url)
        data = json.loads(raw)

        results = []

        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", "Summary"),
                "url": data.get("AbstractURL", ""),
                "snippet": data["AbstractText"]
            })

        for topic in data.get("RelatedTopics", []):
            if len(results) >= max_results:
                break
            if "Text" in topic and "FirstURL" in topic:
                results.append({
                    "title": topic["Text"][:80],
                    "url": topic["FirstURL"],
                    "snippet": topic["Text"]
                })
            elif "Topics" in topic:
                for sub in topic["Topics"]:
                    if len(results) >= max_results:
                        break
                    if "Text" in sub and "FirstURL" in sub:
                        results.append({
                            "title": sub["Text"][:80],
                            "url": sub["FirstURL"],
                            "snippet": sub["Text"]
                        })

        if not results:
            return {"status": "no_results", "message": f"No results for '{query}'."}

        return {"status": "success", "query": query, "results": results[:max_results]}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ---------------------------------------------------------
# Fetch and clean a web page
# ---------------------------------------------------------
def run_fetch_page(payload: dict):
    url = payload.get("url", "")
    max_chars = payload.get("max_chars", 3000)

    try:
        raw = http_get(url)

        if BS4_AVAILABLE:
            soup = BeautifulSoup(raw, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            text = soup.get_text(separator=" ")
        else:
            text = strip_html(raw)

        text = re.sub(r"\s+", " ", text).strip()

        if len(text) > max_chars:
            text = text[:max_chars] + f"... [truncated at {max_chars} chars]"

        return {"status": "success", "url": url, "content": text}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ---------------------------------------------------------
# Weather via wttr.in
# ---------------------------------------------------------
def run_get_weather(payload: dict):
    location = payload.get("location", "")

    try:
        encoded = urllib.parse.quote(location)
        url = f"https://wttr.in/{encoded}?format=j1"
        raw = http_get(url)
        data = json.loads(raw)

        current = data["current_condition"][0]
        area = data["nearest_area"][0]
        area_name = area["areaName"][0]["value"]
        country = area["country"][0]["value"]

        return {
            "status": "success",
            "location": f"{area_name}, {country}",
            "temperature_f": current["temp_F"],
            "temperature_c": current["temp_C"],
            "feels_like_f": current["FeelsLikeF"],
            "feels_like_c": current["FeelsLikeC"],
            "description": current["weatherDesc"][0]["value"],
            "humidity": current["humidity"] + "%",
            "wind_mph": current["windspeedMiles"] + " mph",
            "wind_dir": current["winddir16Point"],
            "visibility_miles": current["visibility"],
            "uv_index": current["uvIndex"]
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ---------------------------------------------------------
# RSS news feed reader
# ---------------------------------------------------------
def run_get_news(payload: dict):
    source = payload.get("source", "bbc_world")
    max_items = payload.get("max_items", 5)

    try:
        if source in DEFAULT_FEEDS:
            feed_url = DEFAULT_FEEDS[source]
        elif source.startswith("http://") or source.startswith("https://"):
            feed_url = source
        else:
            return {
                "status": "error",
                "message": f"Unknown source '{source}'.",
                "available_feeds": list(DEFAULT_FEEDS.keys())
            }

        raw = http_get(feed_url)
        items = []

        item_blocks = re.findall(r"<item>(.*?)</item>", raw, re.DOTALL)

        for block in item_blocks[:max_items]:
            title = re.search(r"<title>(.*?)</title>", block, re.DOTALL)
            link = re.search(r"<link>(.*?)</link>", block, re.DOTALL)
            desc = re.search(r"<description>(.*?)</description>", block, re.DOTALL)
            pub_date = re.search(r"<pubDate>(.*?)</pubDate>", block, re.DOTALL)

            title_text = strip_html(title.group(1).strip()) if title else "No title"
            link_text = link.group(1).strip() if link else ""
            desc_text = strip_html(desc.group(1).strip())[:200] if desc else ""
            date_text = pub_date.group(1).strip() if pub_date else ""

            # CDATA cleanup
            title_text = re.sub(r"<!

            \[CDATA

            \[(.*?)\]

            \]

            >", r"\1", title_text)
            desc_text = re.sub(r"<!

            \[CDATA

            \[(.*?)\]

            \]

            >", r"\1", desc_text)

            items.append({
                "title": title_text,
                "url": link_text,
                "summary": desc_text,
                "published": date_text
            })

        if not items:
            return {"status": "no_results", "message": "No items found in feed."}

        return {"status": "success", "source": source, "items": items}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ---------------------------------------------------------
# Server Action Map
# ---------------------------------------------------------
ACTIONS = {
    "web_search": run_web_search,
    "fetch_page": run_fetch_page,
    "get_weather": run_get_weather,
    "get_news": run_get_news,
}

# ---------------------------------------------------------
# Entry point for router
# ---------------------------------------------------------
def call(action: str, payload: dict):
    fn = ACTIONS.get(action)
    if not fn:
        return {"status": "error", "message": f"Unknown action '{action}'"}
    return fn(payload)
