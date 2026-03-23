# === Weather Organ — weather_server/server.py ===
# Delegates to internet_server which handles weather via Open-Meteo (free, no key).

from mcp_servers_hub.internet_server.server import handle as internet_handle


def handle(user_input: str) -> dict:
    return internet_handle(user_input)
