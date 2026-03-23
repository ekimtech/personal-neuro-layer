# === Jarvis 4.0 — Home Assistant MCP Organ ===
# Connects to Home Assistant REST API
# Tools: lights, switches, climate, scenes, sensors, locks, automations, covers, media players

import re
import json
import logging
import threading
import requests

logger = logging.getLogger(__name__)

# Load config
try:
    from mcp_servers_hub.home_assistant_server.ha_config import HA_URL, HA_TOKEN
except ImportError:
    HA_URL = "http://192.168.X.X:8123"
    HA_TOKEN = ""
    logger.error("[HomeAssistant] Could not load ha_config.py — check ha_config.py!")


# ---------------------------------------------------------
# Core API helper
# ---------------------------------------------------------

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }


def _get(path: str) -> dict:
    try:
        r = requests.get(f"{HA_URL}/api{path}", headers=_headers(), timeout=10)
        r.raise_for_status()
        return {"ok": True, "data": r.json()}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "Cannot reach Home Assistant. Check HA_URL in ha_config.py."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _post(path: str, payload: dict = None) -> dict:
    try:
        r = requests.post(
            f"{HA_URL}/api{path}",
            headers=_headers(),
            json=payload or {},
            timeout=10
        )
        # Capture body before raise so we can include it in the error
        body = ""
        try:
            body = r.text
        except Exception:
            pass
        r.raise_for_status()
        try:
            return {"ok": True, "data": r.json()}
        except Exception:
            return {"ok": True, "data": body}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "Cannot reach Home Assistant. Check HA_URL in ha_config.py."}
    except requests.exceptions.HTTPError as e:
        return {"ok": False, "error": f"HA returned {e.response.status_code}: {body}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------
# Tool: API health check
# ---------------------------------------------------------

def check_status() -> dict:
    result = _get("/")
    if not result["ok"]:
        return {"status": "error", "data": result["error"]}
    return {"status": "success", "data": "Home Assistant is online and reachable."}


# ---------------------------------------------------------
# Tool: Get all entity states (with optional domain filter)
# ---------------------------------------------------------

def get_states(domain: str = None) -> dict:
    result = _get("/states")
    if not result["ok"]:
        return {"status": "error", "data": result["error"]}

    states = result["data"]
    if domain:
        states = [s for s in states if s["entity_id"].startswith(f"{domain}.")]

    if not states:
        label = f"{domain} entities" if domain else "entities"
        return {"status": "success", "data": f"No {label} found in Home Assistant."}

    lines = []
    for s in states:
        entity_id = s.get("entity_id", "")
        state = s.get("state", "unknown")
        friendly = s.get("attributes", {}).get("friendly_name", entity_id)
        lines.append(f"{friendly} ({entity_id}): {state}")

    return {"status": "success", "data": "\n".join(lines)}


# ---------------------------------------------------------
# Tool: Get single entity state
# ---------------------------------------------------------

def get_entity_state(entity_id: str) -> dict:
    result = _get(f"/states/{entity_id}")
    if not result["ok"]:
        return {"status": "error", "data": result["error"]}

    s = result["data"]
    friendly = s.get("attributes", {}).get("friendly_name", entity_id)
    state = s.get("state", "unknown")
    attrs = s.get("attributes", {})

    details = [f"{friendly} is currently {state}."]

    # Add useful attributes if present
    if "brightness" in attrs:
        brightness_pct = round(attrs["brightness"] / 255 * 100)
        details.append(f"Brightness: {brightness_pct}%.")
    if "temperature" in attrs:
        details.append(f"Temperature: {attrs['temperature']}.")
    if "current_temperature" in attrs:
        details.append(f"Current temperature: {attrs['current_temperature']}.")
    if "hvac_mode" in attrs:
        details.append(f"Mode: {attrs['hvac_mode']}.")
    if "battery_level" in attrs:
        details.append(f"Battery: {attrs['battery_level']}%.")

    return {"status": "success", "data": " ".join(details)}


# ---------------------------------------------------------
# Tool: Call any HA service
# ---------------------------------------------------------

def call_service(domain: str, service: str, entity_id: str = None, extra: dict = None) -> dict:
    payload = {}
    if entity_id:
        payload["entity_id"] = entity_id
    if extra:
        payload.update(extra)

    result = _post(f"/services/{domain}/{service}", payload)
    if not result["ok"]:
        return {"status": "error", "data": result["error"]}
    return {"status": "success", "data": result["data"]}


# ---------------------------------------------------------
# Tool: Find entity by fuzzy name match
# ---------------------------------------------------------

def find_entity(name_fragment: str, domain: str = None) -> list:
    result = _get("/states")
    if not result["ok"]:
        return []

    matches = []
    fragment = name_fragment.lower().replace(" ", "_")
    fragment_spaced = name_fragment.lower()

    for s in result["data"]:
        entity_id = s.get("entity_id", "").lower()
        friendly = s.get("attributes", {}).get("friendly_name", "").lower()

        if domain and not entity_id.startswith(f"{domain}."):
            continue

        if fragment in entity_id or fragment_spaced in friendly:
            matches.append(s)

    return matches


# ---------------------------------------------------------
# Tool: List all scenes
# ---------------------------------------------------------

def list_scenes() -> dict:
    result = get_states("scene")
    return result


# ---------------------------------------------------------
# Tool: List all automations
# ---------------------------------------------------------

def list_automations() -> dict:
    result = get_states("automation")
    return result


# ---------------------------------------------------------
# Natural language → entity resolver + action dispatcher
# ---------------------------------------------------------

def _resolve_and_act(text: str, domain: str, on_keywords: list, off_keywords: list,
                     toggle_keywords: list, on_service: str, off_service: str,
                     toggle_service: str) -> dict:
    """
    Generic resolver for light/switch/cover/lock domains.
    Tries to find the entity from the user's words, then calls the right service.
    """
    # Determine action
    if any(k in text for k in off_keywords):
        action = "off"
        service = off_service
    elif any(k in text for k in toggle_keywords):
        action = "toggle"
        service = toggle_service
    else:
        action = "on"
        service = on_service

    # Strip action words to isolate the device name
    strip_words = on_keywords + off_keywords + toggle_keywords + [
        "the", "my", "a", "an", "please", "jarvis", "light", "lights",
        "switch", "fan", "lamp", "bulb", domain
    ]
    name_fragment = text
    for w in strip_words:
        name_fragment = re.sub(rf"\b{re.escape(w)}\b", " ", name_fragment)
    name_fragment = name_fragment.strip()

    # Find matching entities
    matches = find_entity(name_fragment, domain=domain) if name_fragment else find_entity("", domain=domain)

    if not matches:
        # Try all entities in domain
        all_entities = _get("/states")
        if not all_entities["ok"]:
            return {"data": f"Could not reach Home Assistant: {all_entities['error']}"}
        domain_entities = [s for s in all_entities["data"] if s["entity_id"].startswith(f"{domain}.")]
        if not domain_entities:
            return {"data": f"No {domain} entities found in Home Assistant."}
        # If only one entity in domain, use it
        if len(domain_entities) == 1:
            matches = domain_entities
        else:
            names = [s.get("attributes", {}).get("friendly_name", s["entity_id"]) for s in domain_entities]
            return {"data": f"I found multiple {domain} devices. Please specify which one: {', '.join(names)}"}

    # Act on first match (or all if "all" in text)
    if "all" in text:
        entity_ids = [s["entity_id"] for s in matches]
        for eid in entity_ids:
            call_service(domain, service, eid)
        friendly_names = [s.get("attributes", {}).get("friendly_name", s["entity_id"]) for s in matches]
        return {"data": f"Turned {action} {len(entity_ids)} {domain}(s): {', '.join(friendly_names)}."}
    else:
        target = matches[0]
        eid = target["entity_id"]
        friendly = target.get("attributes", {}).get("friendly_name", eid)
        result = call_service(domain, service, eid)
        if result["status"] == "error":
            return {"data": f"Error: {result['data']}"}
        return {"data": f"Turned {action} {friendly}."}


# ---------------------------------------------------------
# Media Player Config
# ---------------------------------------------------------

# HA local media source path for music
# Path: My Media → Storage → Music → ARTIST (all caps) → Album (mixed case)
MUSIC_SOURCE_BASE = "media-source://media_source/local/Storage/Music"

# Cache for discovered entity IDs
_entity_cache = {}


def _discover_cast_entities() -> dict:
    """Query HA and return a dict of media_player entities keyed by friendly name (lowercase)."""
    global _entity_cache
    result = _get("/states")
    if not result["ok"]:
        return {}
    found = {}
    for s in result["data"]:
        eid = s.get("entity_id", "")
        if eid.startswith("media_player."):
            friendly = s.get("attributes", {}).get("friendly_name", eid).lower()
            found[friendly] = eid
    _entity_cache = found
    return found


def _get_default_speaker() -> str:
    """Return the entity ID of the best speaker candidate, with fallback."""
    entities = _discover_cast_entities() if not _entity_cache else _entity_cache
    # Try exact matches first
    for name in ["bedroom speaker", "bedroom", "google home", "speaker"]:
        if name in entities:
            return entities[name]
    # Try partial match on any media_player
    for name, eid in entities.items():
        if "speaker" in name or "home" in name or "mini" in name:
            return eid
    # Last resort: confirmed default
    return "media_player.bedroom_speaker"


# ---------------------------------------------------------
# Tool: Get all media players and their current state
# ---------------------------------------------------------

def get_media_players() -> dict:
    result = _get("/states")
    if not result["ok"]:
        return {"status": "error", "data": result["error"]}

    players = [s for s in result["data"] if s["entity_id"].startswith("media_player.")]
    if not players:
        return {"status": "success", "data": "No media player devices found in Home Assistant."}

    lines = []
    for p in players:
        eid = p["entity_id"]
        state = p.get("state", "unknown")
        attrs = p.get("attributes", {})
        friendly = attrs.get("friendly_name", eid)
        media_title = attrs.get("media_title", "")
        media_artist = attrs.get("media_artist", "")
        volume = attrs.get("volume_level", None)
        vol_str = f" | Volume: {round(volume * 100)}%" if volume is not None else ""
        now_str = f" | Playing: {media_artist} - {media_title}" if media_title else ""
        lines.append(f"{friendly} ({eid}): {state}{vol_str}{now_str}")

    return {"status": "success", "data": "\n".join(lines)}


# ---------------------------------------------------------
# Tool: What is currently playing
# ---------------------------------------------------------

def now_playing(entity_id: str = None) -> dict:
    eid = entity_id or DEFAULT_SPEAKER
    result = _get(f"/states/{eid}")
    if not result["ok"]:
        return {"status": "error", "data": result["error"]}

    s = result["data"]
    state = s.get("state", "unknown")
    attrs = s.get("attributes", {})
    friendly = attrs.get("friendly_name", eid)

    if state in ("idle", "off", "unavailable", "standby"):
        return {"status": "success", "data": f"{friendly} is {state}. Nothing is playing."}

    title = attrs.get("media_title", "")
    artist = attrs.get("media_artist", "")
    album = attrs.get("media_album_name", "")
    volume = attrs.get("volume_level", None)
    shuffle = attrs.get("shuffle", None)

    parts = [f"{friendly} is {state}."]
    if artist and title:
        parts.append(f"Now playing: {artist} - {title}.")
    elif title:
        parts.append(f"Now playing: {title}.")
    if album:
        parts.append(f"Album: {album}.")
    if volume is not None:
        parts.append(f"Volume: {round(volume * 100)}%.")
    if shuffle is not None:
        parts.append(f"Shuffle is {'on' if shuffle else 'off'}.")

    return {"status": "success", "data": " ".join(parts)}


# ---------------------------------------------------------
# Tool: Resolve which cast device the user means
# ---------------------------------------------------------

def _resolve_cast_device(text: str) -> str:
    # Onn Box = preferred media player for the TV
    if any(k in text for k in ["onn", "onn box", "streaming box"]):
        return "media_player.bedroom_tv_onn_box"
    if any(k in text for k in ["bedroom tv", "television", "on the tv", "on tv", "tv"]):
        return "media_player.bedroom_tv_onn_box"
    if any(k in text for k in ["bedroom speaker", "speaker", "google home", "home speaker"]):
        return "media_player.bedroom_speaker"
    return "media_player.bedroom_speaker"


# ---------------------------------------------------------
# Tool: Play music by artist or album name
# ---------------------------------------------------------

def _ws_browse_album(entity_id: str, content_id: str) -> list:
    """
    Use HA WebSocket API to browse a media folder and return its children.
    Returns a list of track dicts with media_content_id, media_content_type, title.
    """
    try:
        import websocket
    except ImportError:
        logger.error("[HA] websocket-client not installed. Run: pip install websocket-client")
        return []

    tracks = []
    done = threading.Event()
    req_id = 2  # 1 = auth

    ws_url = HA_URL.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"

    def on_message(ws, message):
        try:
            data = json.loads(message)
            t = data.get("type")

            if t == "auth_required":
                ws.send(json.dumps({"type": "auth", "access_token": HA_TOKEN}))

            elif t == "auth_ok":
                ws.send(json.dumps({
                    "id": req_id,
                    "type": "media_player/browse_media",
                    "entity_id": entity_id,
                    "media_content_type": "app",
                    "media_content_id": content_id
                }))

            elif t == "result" and data.get("id") == req_id:
                if data.get("success"):
                    children = data.get("result", {}).get("children", [])
                    tracks.extend(children)
                    logger.info(f"[HA] WS browse returned {len(children)} items")
                else:
                    logger.warning(f"[HA] WS browse error: {data.get('error')}")
                done.set()
                ws.close()
        except Exception as e:
            logger.error(f"[HA] WS message error: {e}")
            done.set()

    def on_error(ws, error):
        logger.error(f"[HA] WS error: {error}")
        done.set()

    def on_close(ws, *args):
        done.set()

    try:
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        t = threading.Thread(target=ws.run_forever)
        t.daemon = True
        t.start()
        done.wait(timeout=10)
    except Exception as e:
        logger.error(f"[HA] WS connect error: {e}")

    return tracks


def play_music(query: str, entity_id: str = None) -> dict:
    """
    Play music via Music Assistant (mass.play_media).
    query is either "ARTIST" or "ARTIST/Album Name" (from the handle patterns).
    Converts ALL CAPS artist names to Title Case for Music Assistant search.
    """
    eid = entity_id or "media_player.bedroom_speaker"
    logger.info(f"[HA] play_music query='{query}' entity={eid}")

    if "/" in query:
        # Artist + specific album
        parts      = query.split("/", 1)
        artist     = parts[0].strip().title()   # "JOSH GROBAN" → "Josh Groban"
        album      = parts[1].strip()           # "Live at the Greek"
        media_id   = album
        media_type = "album"
        display    = f"{album} by {artist}"
    else:
        # Artist only — play everything by them
        artist     = query.strip().title()      # "MICHAEL JACKSON" → "Michael Jackson"
        media_id   = artist
        media_type = "artist"
        display    = artist

    logger.info(f"[HA] mass.play_media → media_id='{media_id}' type={media_type} entity={eid}")

    result = call_service("mass", "play_media", eid, {
        "media_id":   media_id,
        "media_type": media_type,
        "enqueue":    "replace"
    })

    if result["status"] == "success":
        return {"status": "success", "data": f"Playing {display} on your speaker."}

    return {
        "status": "error",
        "data": (
            f"Couldn't play {display}. Make sure Music Assistant is running "
            f"and '{media_id}' exists in your library."
        )
    }


# ---------------------------------------------------------
# Tool: Playback controls (pause, resume, stop, next, prev)
# ---------------------------------------------------------

def media_control(command: str, entity_id: str = None) -> dict:
    eid = entity_id or DEFAULT_SPEAKER

    service_map = {
        "pause":    ("media_player", "media_pause"),
        "resume":   ("media_player", "media_play"),
        "play":     ("media_player", "media_play"),
        "stop":     ("media_player", "media_stop"),
        "next":     ("media_player", "media_next_track"),
        "previous": ("media_player", "media_previous_track"),
        "prev":     ("media_player", "media_previous_track"),
    }

    if command not in service_map:
        return {"status": "error", "data": f"Unknown media command: {command}"}

    domain, service = service_map[command]
    result = call_service(domain, service, eid)
    if result["status"] == "error":
        return {"status": "error", "data": result["data"]}

    state_res = _get(f"/states/{eid}")
    friendly = eid
    if state_res["ok"]:
        friendly = state_res["data"].get("attributes", {}).get("friendly_name", eid)

    labels = {
        "pause": "Paused", "resume": "Resumed", "play": "Resumed",
        "stop": "Stopped", "next": "Skipped to next track",
        "previous": "Went back to previous track", "prev": "Went back to previous track"
    }
    return {"status": "success", "data": f"{labels[command]} on {friendly}."}


# ---------------------------------------------------------
# Tool: Set volume
# ---------------------------------------------------------

def set_volume(level: float, entity_id: str = None) -> dict:
    """level: 0.0 to 1.0"""
    eid = entity_id or DEFAULT_SPEAKER
    result = call_service("media_player", "volume_set", eid, {"volume_level": round(level, 2)})
    if result["status"] == "error":
        return {"status": "error", "data": result["data"]}

    state_res = _get(f"/states/{eid}")
    friendly = eid
    if state_res["ok"]:
        friendly = state_res["data"].get("attributes", {}).get("friendly_name", eid)

    return {"status": "success", "data": f"Volume set to {round(level * 100)}% on {friendly}."}


# ---------------------------------------------------------
# Tool: Volume up / down by increment
# ---------------------------------------------------------

def adjust_volume(direction: str, amount: float = 0.1, entity_id: str = None) -> dict:
    eid = entity_id or DEFAULT_SPEAKER
    state_res = _get(f"/states/{eid}")
    if not state_res["ok"]:
        return {"status": "error", "data": state_res["error"]}

    current = state_res["data"].get("attributes", {}).get("volume_level", 0.5)
    friendly = state_res["data"].get("attributes", {}).get("friendly_name", eid)

    if direction == "up":
        new_vol = min(1.0, current + amount)
    else:
        new_vol = max(0.0, current - amount)

    result = call_service("media_player", "volume_set", eid, {"volume_level": round(new_vol, 2)})
    if result["status"] == "error":
        return {"status": "error", "data": result["data"]}

    return {"status": "success", "data": f"Volume {direction} to {round(new_vol * 100)}% on {friendly}."}


# ---------------------------------------------------------
# Tool: Shuffle toggle
# ---------------------------------------------------------

def set_shuffle(enabled: bool, entity_id: str = None) -> dict:
    eid = entity_id or DEFAULT_SPEAKER
    result = call_service("media_player", "shuffle_set", eid, {"shuffle": enabled})
    if result["status"] == "error":
        return {"status": "error", "data": result["data"]}
    label = "on" if enabled else "off"
    return {"status": "success", "data": f"Shuffle turned {label}."}


# ---------------------------------------------------------
# MCP Router handle function
# ---------------------------------------------------------

def handle(user_input: str) -> dict:
    try:
        return _handle_inner(user_input)
    except Exception as e:
        logger.exception("[HA] Unhandled exception in handle()")
        return {"data": f"Home Assistant organ error: {str(e)}"}


def _handle_inner(user_input: str) -> dict:
    text = user_input.lower().strip()

    # --- Media Players: list devices ---
    if any(k in text for k in ["list media players", "what speakers", "what media players", "show media devices", "cast devices"]):
        result = get_media_players()
        return {"data": result["data"]}

    # --- Media Players: what's playing ---
    if any(k in text for k in ["what's playing", "whats playing", "now playing", "what is playing", "what song", "what track"]):
        eid = _resolve_cast_device(text)
        result = now_playing(eid)
        return {"data": result["data"]}

    # --- Media: Play music by artist or album ---
    if text.startswith("play ") and not any(k in text for k in ["play media player", "play scene", "play automation"]):
        eid = _resolve_cast_device(text)

        # Work on original input to preserve exact casing for folder matching
        original = user_input.strip()

        # Strip device references (case-insensitive)
        for strip in ["on the bedroom speaker", "on the bedroom tv", "on bedroom speaker",
                      "on bedroom tv", "on the speaker", "on the tv", "on speaker", "on tv",
                      "on google home", "on my speaker", "On the Bedroom Speaker",
                      "On the Bedroom TV", "On Bedroom Speaker", "On Bedroom TV"]:
            original = re.sub(re.escape(strip), "", original, flags=re.IGNORECASE).strip()

        # Remove leading "play" (case-insensitive)
        original = re.sub(r"(?i)^play\s+", "", original).strip()

        if not original:
            return {"data": "What would you like me to play? Say 'play Miles Davis' or 'play Live at the Greek by Josh Groban'."}

        # Generic words that mean "play anything by artist" — not album names
        _GENERIC_WORDS = {
            "music", "something", "songs", "a song", "anything",
            "some music", "some songs", "a track", "tracks", "stuff",
            "anything good", "some", "anything by"
        }

        # Pattern 1: "[album] by [artist]"  →  ARTIST/Album (preserve user casing)
        by_match = re.match(r"^(.+?)\s+by\s+(.+)$", original, re.IGNORECASE)
        if by_match:
            album  = by_match.group(1).strip()
            artist = by_match.group(2).strip().upper()
            # If "album" is just a generic word, treat as artist-only
            if album.lower() in _GENERIC_WORDS:
                result = play_music(artist, eid)
            else:
                result = play_music(f"{artist}/{album}", eid)
            return {"data": result["data"]}

        # Pattern 2: "[artist]'s [album]"  →  ARTIST/Album
        poss_match = re.match(r"^(.+?)(?:'s|s')\s+(.+)$", original, re.IGNORECASE)
        if poss_match:
            artist = poss_match.group(1).strip().upper()
            album  = poss_match.group(2).strip()
            result = play_music(f"{artist}/{album}", eid)
            return {"data": result["data"]}

        # Pattern 3: "[artist] album [album]"  →  ARTIST/Album
        album_kw_match = re.match(r"^(.+?)\s+album\s+(.+)$", original, re.IGNORECASE)
        if album_kw_match:
            artist = album_kw_match.group(1).strip().upper()
            album  = album_kw_match.group(2).strip()
            result = play_music(f"{artist}/{album}", eid)
            return {"data": result["data"]}

        # Pattern 4: artist only  →  ARTIST folder (plays all)
        result = play_music(original.upper(), eid)
        return {"data": result["data"]}

    # --- Media: Pause ---
    if any(k in text for k in ["pause", "pause the music", "pause music"]):
        eid = _resolve_cast_device(text)
        result = media_control("pause", eid)
        return {"data": result["data"]}

    # --- Media: Resume ---
    if any(k in text for k in ["resume", "resume music", "resume the music", "unpause", "continue playing"]):
        eid = _resolve_cast_device(text)
        result = media_control("resume", eid)
        return {"data": result["data"]}

    # --- Media: Stop ---
    if any(k in text for k in ["stop the music", "stop music", "stop playing", "stop playback"]):
        eid = _resolve_cast_device(text)
        result = media_control("stop", eid)
        return {"data": result["data"]}

    # --- Media: Next track ---
    if any(k in text for k in ["next track", "next song", "skip", "skip song", "skip track"]):
        eid = _resolve_cast_device(text)
        result = media_control("next", eid)
        return {"data": result["data"]}

    # --- Media: Previous track ---
    if any(k in text for k in ["previous track", "previous song", "go back", "last song", "last track", "prev"]):
        eid = _resolve_cast_device(text)
        result = media_control("previous", eid)
        return {"data": result["data"]}

    # --- Media: Set volume to specific % ---
    vol_match = re.search(r"volume\s+(?:to\s+)?(\d+)\s*(?:%|percent)?", text)
    if vol_match and any(k in text for k in ["set volume", "volume to", "volume at"]):
        eid = _resolve_cast_device(text)
        level = int(vol_match.group(1)) / 100
        result = set_volume(level, eid)
        return {"data": result["data"]}

    # --- Media: Volume up / down ---
    if any(k in text for k in ["volume up", "louder", "turn it up", "turn up"]):
        eid = _resolve_cast_device(text)
        result = adjust_volume("up", 0.1, eid)
        return {"data": result["data"]}

    if any(k in text for k in ["volume down", "quieter", "turn it down", "turn down", "lower the volume"]):
        eid = _resolve_cast_device(text)
        result = adjust_volume("down", 0.1, eid)
        return {"data": result["data"]}

    # --- Media: Shuffle ---
    if any(k in text for k in ["shuffle on", "turn on shuffle", "enable shuffle", "shuffle my music"]):
        eid = _resolve_cast_device(text)
        result = set_shuffle(True, eid)
        return {"data": result["data"]}

    if any(k in text for k in ["shuffle off", "turn off shuffle", "disable shuffle", "no shuffle"]):
        eid = _resolve_cast_device(text)
        result = set_shuffle(False, eid)
        return {"data": result["data"]}

    # --- Status / ping ---
    if any(k in text for k in ["home assistant status", "is home assistant", "ha status", "ping home"]):
        result = check_status()
        return {"data": result["data"]}

    # --- List all devices / entities ---
    if any(k in text for k in ["list all", "show all", "what devices", "all devices", "all entities"]):
        domain = None
        if "light" in text:
            domain = "light"
        elif "switch" in text:
            domain = "switch"
        elif "scene" in text:
            domain = "scene"
        elif "automation" in text:
            domain = "automation"
        elif "climate" in text or "thermostat" in text:
            domain = "climate"
        elif "sensor" in text:
            domain = "sensor"
        elif "cover" in text or "blind" in text or "garage" in text:
            domain = "cover"
        elif "lock" in text:
            domain = "lock"

        result = get_states(domain)
        return {"data": result["data"]}

    # --- Scenes ---
    if any(k in text for k in ["scene", "activate", "movie mode", "night mode", "morning"]):
        if any(k in text for k in ["list", "show", "what scenes"]):
            result = list_scenes()
            return {"data": result["data"]}

        # Try to find and activate a scene
        strip_words = ["activate", "scene", "turn on", "enable", "set", "the", "my"]
        name_fragment = text
        for w in strip_words:
            name_fragment = re.sub(rf"\b{re.escape(w)}\b", " ", name_fragment)
        name_fragment = name_fragment.strip()

        matches = find_entity(name_fragment, domain="scene")
        if matches:
            scene = matches[0]
            eid = scene["entity_id"]
            friendly = scene.get("attributes", {}).get("friendly_name", eid)
            result = call_service("scene", "turn_on", eid)
            if result["status"] == "error":
                return {"data": f"Error activating scene: {result['data']}"}
            return {"data": f"Scene activated: {friendly}."}
        return {"data": "I couldn't find that scene. Try 'list all scenes' to see what's available."}

    # --- Automations ---
    if any(k in text for k in ["automation", "routine", "trigger"]):
        if any(k in text for k in ["list", "show", "what automations"]):
            result = list_automations()
            return {"data": result["data"]}

        strip_words = ["trigger", "run", "activate", "automation", "routine", "the", "my"]
        name_fragment = text
        for w in strip_words:
            name_fragment = re.sub(rf"\b{re.escape(w)}\b", " ", name_fragment)
        name_fragment = name_fragment.strip()

        matches = find_entity(name_fragment, domain="automation")
        if matches:
            auto = matches[0]
            eid = auto["entity_id"]
            friendly = auto.get("attributes", {}).get("friendly_name", eid)
            result = call_service("automation", "trigger", eid)
            if result["status"] == "error":
                return {"data": f"Error triggering automation: {result['data']}"}
            return {"data": f"Triggered automation: {friendly}."}
        return {"data": "I couldn't find that automation. Try 'list all automations' to see what's available."}

    # --- Climate / Thermostat ---
    if any(k in text for k in ["thermostat", "climate", "temperature", "heat", "cool", "hvac", "air"]):
        # Set temperature
        temp_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:degrees?|°)?", text)
        if temp_match and any(k in text for k in ["set", "change", "to"]):
            temp = float(temp_match.group(1))
            matches = find_entity("", domain="climate")
            if matches:
                eid = matches[0]["entity_id"]
                friendly = matches[0].get("attributes", {}).get("friendly_name", eid)
                result = call_service("climate", "set_temperature", eid, {"temperature": temp})
                if result["status"] == "error":
                    return {"data": f"Error: {result['data']}"}
                return {"data": f"Set {friendly} to {temp} degrees."}

        # Set mode
        if "heat" in text:
            matches = find_entity("", domain="climate")
            if matches:
                eid = matches[0]["entity_id"]
                result = call_service("climate", "set_hvac_mode", eid, {"hvac_mode": "heat"})
                return {"data": "Thermostat set to heat mode."}
        if "cool" in text:
            matches = find_entity("", domain="climate")
            if matches:
                eid = matches[0]["entity_id"]
                result = call_service("climate", "set_hvac_mode", eid, {"hvac_mode": "cool"})
                return {"data": "Thermostat set to cool mode."}
        if any(k in text for k in ["off", "turn off"]):
            matches = find_entity("", domain="climate")
            if matches:
                eid = matches[0]["entity_id"]
                result = call_service("climate", "set_hvac_mode", eid, {"hvac_mode": "off"})
                return {"data": "Thermostat turned off."}

        # Query state
        result = get_states("climate")
        return {"data": result["data"]}

    # --- Locks ---
    if any(k in text for k in ["lock", "unlock", "door lock", "deadbolt"]):
        if any(k in text for k in ["unlock", "open"]):
            return _resolve_and_act(
                text, "lock",
                on_keywords=["unlock", "open"],
                off_keywords=["lock", "secure"],
                toggle_keywords=[],
                on_service="unlock",
                off_service="lock",
                toggle_service="lock"
            )
        else:
            return _resolve_and_act(
                text, "lock",
                on_keywords=["lock", "secure"],
                off_keywords=["unlock", "open"],
                toggle_keywords=[],
                on_service="lock",
                off_service="unlock",
                toggle_service="lock"
            )

    # --- Covers (garage, blinds, shutters) ---
    if any(k in text for k in ["garage", "blind", "shutter", "cover", "curtain"]):
        if any(k in text for k in ["open", "raise", "up"]):
            return _resolve_and_act(
                text, "cover",
                on_keywords=["open", "raise", "up"],
                off_keywords=["close", "lower", "down"],
                toggle_keywords=["toggle"],
                on_service="open_cover",
                off_service="close_cover",
                toggle_service="toggle"
            )
        else:
            return _resolve_and_act(
                text, "cover",
                on_keywords=["close", "lower", "down"],
                off_keywords=["open", "raise", "up"],
                toggle_keywords=["toggle"],
                on_service="close_cover",
                off_service="open_cover",
                toggle_service="toggle"
            )

    # --- Lights with brightness ---
    if any(k in text for k in ["light", "lights", "lamp", "bulb", "dim", "bright"]):
        # Brightness control
        brightness_match = re.search(r"(\d+)\s*(?:%|percent)", text)
        if brightness_match:
            brightness_pct = int(brightness_match.group(1))
            brightness_val = round(brightness_pct / 100 * 255)

            strip_words = ["set", "dim", "brighten", "change", "to", "the", "my", "light", "lights", "at", "percent", "%"]
            name_fragment = text
            for w in strip_words:
                name_fragment = re.sub(rf"\b{re.escape(w)}\b", " ", name_fragment)
            name_fragment = re.sub(r"\d+", "", name_fragment).strip()

            matches = find_entity(name_fragment, domain="light") if name_fragment else find_entity("", domain="light")
            if matches:
                eid = matches[0]["entity_id"]
                friendly = matches[0].get("attributes", {}).get("friendly_name", eid)
                result = call_service("light", "turn_on", eid, {"brightness": brightness_val})
                if result["status"] == "error":
                    return {"data": f"Error: {result['data']}"}
                return {"data": f"Set {friendly} brightness to {brightness_pct}%."}

        return _resolve_and_act(
            text, "light",
            on_keywords=["turn on", "on", "enable", "bright"],
            off_keywords=["turn off", "off", "disable", "dim"],
            toggle_keywords=["toggle", "switch"],
            on_service="turn_on",
            off_service="turn_off",
            toggle_service="toggle"
        )

    # --- Switches ---
    if any(k in text for k in ["switch", "plug", "outlet", "fan", "power"]):
        return _resolve_and_act(
            text, "switch",
            on_keywords=["turn on", "on", "enable", "start"],
            off_keywords=["turn off", "off", "disable", "stop"],
            toggle_keywords=["toggle"],
            on_service="turn_on",
            off_service="turn_off",
            toggle_service="toggle"
        )

    # --- Sensor queries ---
    if any(k in text for k in ["sensor", "temperature in", "humidity", "motion", "battery", "energy", "power usage"]):
        strip_words = ["what is", "what's", "the", "sensor", "in", "of", "my", "show", "check", "jarvis"]
        name_fragment = text
        for w in strip_words:
            name_fragment = re.sub(rf"\b{re.escape(w)}\b", " ", name_fragment)
        name_fragment = name_fragment.strip()

        matches = find_entity(name_fragment, domain="sensor") if name_fragment else []
        if matches:
            eid = matches[0]["entity_id"]
            return {"data": get_entity_state(eid)["data"]}

        result = get_states("sensor")
        return {"data": result["data"]}

    # --- Generic entity state query ---
    if any(k in text for k in ["is the", "is my", "what is", "status of", "state of", "check"]):
        # Try to extract entity name and find it
        strip_words = ["is the", "is my", "what is", "status of", "state of", "check", "the", "my"]
        name_fragment = text
        for w in strip_words:
            name_fragment = re.sub(rf"\b{re.escape(w)}\b", " ", name_fragment)
        name_fragment = name_fragment.strip()

        if name_fragment:
            matches = find_entity(name_fragment)
            if matches:
                eid = matches[0]["entity_id"]
                return {"data": get_entity_state(eid)["data"]}

    # --- Default: show HA overview ---
    lights = get_states("light")
    switches = get_states("switch")
    climate = get_states("climate")

    summary_parts = []
    all_states = _get("/states")
    if all_states["ok"]:
        entities = all_states["data"]
        domains = {}
        for s in entities:
            d = s["entity_id"].split(".")[0]
            domains[d] = domains.get(d, 0) + 1
        domain_summary = ", ".join(f"{count} {d}(s)" for d, count in sorted(domains.items()))
        summary_parts.append(f"Home Assistant is connected. Found: {domain_summary}.")
        summary_parts.append("You can control lights, switches, climate, scenes, automations, locks, and covers.")
    else:
        summary_parts.append(f"Home Assistant error: {all_states['error']}")

    return {"data": " ".join(summary_parts)}
