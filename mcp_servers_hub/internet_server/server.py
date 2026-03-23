# === Internet Organ — internet_server/server.py ===
# Wired 03-18-26 — delegates to search, weather, fetch, news submodules.
# No API keys required — DuckDuckGo + Open-Meteo (free, unlimited).

import re
import logging

from .weather import get_weather, WeatherError
from .search import web_search, SearchError
from .fetch import fetch_page, FetchError
from .news import get_news, NewsError
from .utils import extract_url

logger = logging.getLogger("internet_server")

# --- Default location for bare weather queries ---
DEFAULT_LOCATION = "New York, NY"  # Change this to your city


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _extract_location(text: str) -> str:
    """Pull a location out of a weather query, or return default."""
    patterns = [
        r"weather (?:in|for|at|around) (.+)",
        r"forecast (?:in|for|at) (.+)",
        r"temperature (?:in|for|at) (.+)",
        r"(?:is it|will it) (?:rain|snow|be sunny|be hot|be cold)(?: in| at)? (.+)",
        r"(.+) weather",
        r"(.+) forecast",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            loc = m.group(1).strip().rstrip("?.,!")
            if loc and len(loc) > 1:
                return loc
    return DEFAULT_LOCATION


def _format_weather(data: dict) -> str:
    loc       = data.get("location_name", "Unknown")
    cur       = data.get("current", {})
    temp      = cur.get("temperature")
    humidity  = cur.get("humidity")
    wind      = cur.get("wind_speed")
    units     = data.get("units", "imperial")
    t_sym     = "°F" if units == "imperial" else "°C"
    w_unit    = "mph" if units == "imperial" else "km/h"

    parts = [f"Current weather in {loc}"]
    if temp      is not None: parts.append(f"{temp}{t_sym}")
    if humidity  is not None: parts.append(f"Humidity {humidity}%")
    if wind      is not None: parts.append(f"Wind {wind} {w_unit}")

    forecast = data.get("forecast", [])
    valid = [f["temperature"] for f in forecast if f.get("temperature") is not None]
    if valid:
        parts.append(f"Today's range: {min(valid)}{t_sym} — {max(valid)}{t_sym}")

    return ". ".join(parts) + "."


def _format_search(data: dict) -> str:
    results = data.get("results", [])
    if not results:
        return f"No results found for: {data.get('query', '')}"

    lines = [f"Search results for '{data.get('query', '')}':"]
    for i, r in enumerate(results[:3], 1):
        snippet = r.get("snippet") or r.get("title", "")
        url     = r.get("url", "")
        lines.append(f"{i}. {snippet[:180]}  ({url})")

    return "\n".join(lines)


def _format_news(data: dict) -> str:
    results = data.get("results", [])
    if not results:
        return "No news found right now."

    lines = ["Here are the latest headlines:"]
    for i, r in enumerate(results[:5], 1):
        title   = r.get("title", "")
        snippet = r.get("snippet", "")
        source  = r.get("source", "")
        url     = r.get("url", "")
        line = f"{i}. {title}"
        if source:
            line += f" ({source})"
        if snippet:
            line += f" — {snippet[:120]}"
        if url:
            line += f"\n   {url}"
        lines.append(line)

    return "\n".join(lines)


# ---------------------------------------------------------
# Main handle()
# ---------------------------------------------------------

def handle(user_input: str) -> dict:
    text = user_input.lower().strip()

    # --- Weather ---
    if any(k in text for k in [
        "weather", "forecast", "temperature", "rain", "raining",
        "sunny", "cloudy", "humid", "humidity", "snow", "snowing",
        "wind", "cold outside", "hot outside"
    ]):
        try:
            location = _extract_location(user_input)
            logger.info(f"[Internet] Weather lookup for: {location}")
            data = get_weather(location)
            return {"data": _format_weather(data)}
        except WeatherError as e:
            logger.error(f"[Internet] Weather error: {e}")
            return {"data": f"Sorry, I could not get weather data. {e}"}

    # --- News / Headlines ---
    if any(k in text for k in [
        "news", "headlines", "what's happening", "whats happening",
        "latest news", "top stories", "breaking news"
    ]):
        try:
            # Strip leading news keywords to get optional topic
            query = re.sub(
                r"^(news(?: about)?|headlines|latest news|top stories|breaking news|what(?:'s| is) happening)\s*",
                "", text
            ).strip()
            logger.info(f"[Internet] News query: '{query or 'top news'}'")
            data = get_news(query or "top news today")
            return {"data": _format_news(data)}
        except NewsError as e:
            logger.error(f"[Internet] News error: {e}")
            return {"data": f"Sorry, could not fetch news. {e}"}

    # --- URL Fetch ---
    url = extract_url(user_input)
    if url:
        try:
            logger.info(f"[Internet] Fetching URL: {url}")
            data = fetch_page(url)
            return {"data": f"From {data['url']}:\n{data['preview']}"}
        except FetchError as e:
            logger.error(f"[Internet] Fetch error: {e}")
            return {"data": f"Could not read that page. {e}"}

    # --- Web Search (default) ---
    try:
        query = user_input
        for prefix in ["search for", "search", "google", "look up", "lookup", "web search", "find me", "find"]:
            if text.startswith(prefix):
                query = user_input[len(prefix):].strip()
                break

        logger.info(f"[Internet] Web search: '{query}'")
        data = web_search(query)
        return {"data": _format_search(data)}
    except SearchError as e:
        logger.error(f"[Internet] Search error: {e}")
        return {"data": f"Search failed. {e}"}
