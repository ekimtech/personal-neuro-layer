# internet_server/weather.py

from __future__ import annotations
import requests

class WeatherError(Exception):
    pass

def geocode_location(location: str) -> dict:
    """Resolve a free‑form location string into lat/lon using Open‑Meteo geocoding."""

    # --- Normalize location for Open‑Meteo ---
    loc = location.strip()

    # Remove commas
    loc = loc.replace(",", "")

    # Remove state abbreviations like "FL"
    if loc.lower().endswith(" fl"):
        loc = loc[:-3].strip()

    # Remove full state names like "Florida"
    if loc.lower().endswith(" florida"):
        loc = loc[:-8].strip()

    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": loc, "count": 1}

    r = requests.get(url, params=params, timeout=10)
    if not r.ok:
        raise WeatherError(f"Geocoding failed: HTTP {r.status_code}")

    data = r.json()
    if not data.get("results"):
        raise WeatherError(f"No results found for location: {location}")

    first = data["results"][0]
    return {
        "name": first["name"],
        "latitude": first["latitude"],
        "longitude": first["longitude"],
    }

def get_weather(location: str, units: str = "imperial") -> dict:
    """Return normalized weather data for the given location."""
    geo = geocode_location(location)

    is_metric = units == "metric"
    temp_unit = "celsius" if is_metric else "fahrenheit"
    wind_unit = "kmh" if is_metric else "mph"

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "hourly": "temperature_2m",
        "temperature_unit": temp_unit,
        "wind_speed_unit": wind_unit,
        "forecast_days": 1,
        "timezone": "auto",
    }

    r = requests.get(url, params=params, timeout=10)
    if not r.ok:
        raise WeatherError(f"Weather fetch failed: HTTP {r.status_code}")

    data = r.json()
    current = data.get("current", {})
    hourly = data.get("hourly", {})

    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])

    forecast = []
    for t, temp in zip(times[:6], temps[:6]):
        forecast.append({
            "time": t,
            "temperature": temp,
            "condition": None,  # Open‑Meteo doesn't provide condition text here
        })

    return {
        "location_name": geo["name"],
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "units": units,
        "current": {
            "temperature": current.get("temperature_2m"),
            "feels_like": None,
            "condition": None,
            "humidity": current.get("relative_humidity_2m"),
            "wind_speed": current.get("wind_speed_10m"),
        },
        "forecast": forecast,
        "source": "open-meteo.com",
    }
