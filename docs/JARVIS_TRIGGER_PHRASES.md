# Jarvis 4.0 — Voice & Text Trigger Phrases
*Complete reference for all tools and commands. Last updated: 2026-03-19*

---

## How It Works
Say the wake word **"Jarvis"** followed by any of the phrases below.
You can also type directly into the chat box on the Face panel.
Jarvis matches keywords — you don't have to say the phrase word-for-word.

---

## 🧠 MEMORY
Store and recall information across sessions.

| What to Say | What It Does |
|---|---|
| `remember [anything]` | Saves that info to memory |
| `search memory for [keyword]` | Finds memories matching keyword |
| `delete memory [ID]` | Removes a memory entry by ID (e.g. M0042) |
| `list memory` | Shows all saved memories |

**Examples:**
- *"remember my wife's birthday is June 5th"*
- *"search memory for birthday"*
- *"delete memory M0003"*

---

## 🌤️ WEATHER
Powered by Open-Meteo — no API key needed. Default location set in `internet_server/server.py`.

| What to Say | What It Does |
|---|---|
| `weather` | Current weather for your default location |
| `weather in [city]` | Weather for any city |
| `forecast in [city]` | Extended forecast |
| `temperature in [city]` | Just the temperature |
| `is it raining in [city]` | Rain check |
| `will it snow in [city]` | Snow check |
| `is it hot outside` | Local heat check |
| `is it cold outside` | Local cold check |
| `humidity` | Current humidity |

**Examples:**
- *"what's the weather in New York"*
- *"will it rain in Orlando tomorrow"*
- *"weather forecast for Chicago"*

---

## 🌐 INTERNET / SEARCH
Powered by DuckDuckGo — no API key needed.

| What to Say | What It Does |
|---|---|
| `search for [topic]` | Web search |
| `google [topic]` | Web search |
| `look up [topic]` | Web search |
| `find me [topic]` | Web search |
| `web search [topic]` | Web search |
| `news` | Today's top headlines |
| `latest news` | Top stories |
| `headlines` | Top stories |
| `breaking news` | Breaking news |
| `what's happening` | Current events |
| `fetch [url]` | Reads a web page |

**Examples:**
- *"search for best pizza recipes"*
- *"look up who invented the telephone"*
- *"get the latest news"*

---

## 📧 EMAIL
Connected to your mail server via IMAP/SMTP. Configure in `email_server/.env`.

| What to Say | What It Does |
|---|---|
| `check email` | Shows your last 5 emails |
| `check my email` | Shows your last 5 emails |
| `read my email` | Shows your last 5 emails |
| `show inbox` | Shows your last 5 emails |
| `any new emails` | Shows your last 5 emails |
| `list emails` | Shows your last 5 emails |
| `how many emails` | Count of inbox messages |
| `email count` | Count of inbox messages |
| `send email to [address] saying [message]` | Sends an email |
| `send email to [address] subject [subject] saying [message]` | Sends with subject |
| `email [address] saying [message]` | Quick send |

**Examples:**
- *"check my email"*
- *"how many emails do I have"*
- *"send email to john@example.com saying dinner is at 7"*
- *"send email to mom@gmail.com subject happy birthday saying hope you have a great day"*

---

## 📄 DOCUMENTS
Generates professional PDFs (Invoice, Estimate, Letter) via WeasyPrint.

| What to Say | What It Does |
|---|---|
| `generate invoice` | Opens the invoice form |
| `create invoice` | Opens the invoice form |
| `make invoice` | Opens the invoice form |
| `new invoice` | Opens the invoice form |
| `bill` | Opens the invoice form |
| `generate estimate` | Opens the estimate form |
| `create estimate` | Opens the estimate form |
| `make estimate` | Opens the estimate form |
| `quote` | Opens the estimate form |
| `write letter` | Opens the letter form |
| `create letter` | Opens the letter form |
| `generate letter` | Opens the letter form |
| `compose letter` | Opens the letter form |
| `show my documents` | Lists saved PDFs |
| `list documents` | Lists saved PDFs |
| `saved documents` | Lists saved PDFs |

**Examples:**
- *"generate invoice"*
- *"create a new estimate"*
- *"write a letter"*
- *"show me my documents"*

---

## 🏠 HOME ASSISTANT
Controls your smart home devices via Home Assistant. Configure IP in `home_assistant_server/ha_config.py`.

### Media / Music
| What to Say | What It Does |
|---|---|
| `play [artist]` | Plays artist folder on Bedroom Speaker |
| `play [album] by [artist]` | Plays specific album |
| `play [artist]'s [album]` | Plays specific album |
| `play [artist] album [album]` | Plays specific album |
| `play [anything] on the bedroom tv` | Plays on TV/Onn Box |
| `play [anything] on the bedroom speaker` | Plays on Google Home |
| `pause` / `pause music` | Pauses playback |
| `resume` / `resume music` | Resumes playback |
| `stop music` / `stop playing` | Stops playback |
| `next track` / `next song` / `skip` | Skips to next song |
| `previous track` / `last song` | Goes back one track |
| `volume up` / `louder` / `turn it up` | Volume +10% |
| `volume down` / `quieter` / `turn it down` | Volume -10% |
| `set volume to [0-100]` | Sets exact volume % |
| `volume to 50` | Sets volume to 50% |
| `shuffle on` / `enable shuffle` | Turns shuffle on |
| `shuffle off` / `disable shuffle` | Turns shuffle off |
| `what's playing` / `now playing` | What's on right now |
| `what song is this` | Current track info |
| `list media players` | Shows all Cast devices + status |
| `what speakers do I have` | Shows all Cast devices |

**Examples:**
- *"play Josh Groban"*
- *"play Live at the Greek by Josh Groban"*
- *"play Josh Groban's Live at the Greek on the bedroom speaker"*
- *"volume to 60"*
- *"next song"*
- *"what's playing"*

### Lights
| What to Say | What It Does |
|---|---|
| `turn on the [room] light` | Turns on a light |
| `turn off the [room] light` | Turns off a light |
| `dim the [room] light` | Dims a light |
| `brighten the [room] light` | Brightens a light |
| `set [room] light to [50%]` | Sets brightness % |
| `toggle the [room] light` | Toggles a light |
| `turn on all lights` | Turns on all lights |
| `turn off all lights` | Turns off all lights |
| `list all lights` | Shows all lights + states |

### Switches / Outlets / Fans
| What to Say | What It Does |
|---|---|
| `turn on the [device]` | Turns on a switch |
| `turn off the [device]` | Turns off a switch |
| `toggle the [device]` | Toggles a switch |
| `list all switches` | Shows all switches |

### Climate / Thermostat
| What to Say | What It Does |
|---|---|
| `set thermostat to [72] degrees` | Sets temperature |
| `set heat to [70]` | Sets heat mode + temp |
| `set cool to [72]` | Sets cool mode + temp |
| `turn off thermostat` | Turns off HVAC |
| `what's the thermostat` | Shows current climate state |
| `list all climate` | Shows all climate devices |

### Scenes & Automations
| What to Say | What It Does |
|---|---|
| `activate [scene name]` | Activates a scene |
| `list all scenes` | Shows all scenes |
| `trigger [automation name]` | Runs an automation |
| `list all automations` | Shows all automations |

### Locks & Covers
| What to Say | What It Does |
|---|---|
| `lock the [door]` | Locks a door |
| `unlock the [door]` | Unlocks a door |
| `open the garage` | Opens the garage |
| `close the garage` | Closes the garage |
| `open the blinds` | Opens blinds/covers |
| `close the blinds` | Closes blinds/covers |

### Status / General
| What to Say | What It Does |
|---|---|
| `home assistant status` | Checks HA is online |
| `list all devices` | Shows everything in HA |
| `what devices do I have` | Shows all entities |
| `is the [device] on` | Checks a device state |
| `is my [device] locked` | Checks a lock state |

---

## 📦 QNAP NAS
Manages your QNAP network storage. Configure IP in `qnap_server/qnap_config.py`.

| What to Say | What It Does |
|---|---|
| `qnap status` | NAS health + disk info |
| `nas status` | NAS health + disk info |
| `list shared folders` | Shows network shares |
| `network drive status` | Drive/share info |
| `storage status` | Storage usage |

---

## 🔌 MIKROTIK ROUTER
Manages your MikroTik router via SSH.

| What to Say | What It Does |
|---|---|
| `router status` | CPU, memory, uptime |
| `who is on my network` | Connected devices |
| `connected devices` | List of active connections |
| `block ip [address]` | Adds IP to firewall blocklist |
| `unblock ip [address]` | Removes IP from blocklist |
| `firewall rules` | Shows active firewall rules |
| `mikrotik status` | Router health summary |

**Examples:**
- *"who is on my network"*
- *"block ip 10.0.0.99"*
- *"show connected devices"*

---

## 🔧 SELF-WRITING TOOLS
Jarvis reviews his own code and suggests improvements. You approve before anything changes.

| What to Say | What It Does |
|---|---|
| `review [server name]` | Sends file to LLM for analysis |
| `analyze [server name]` | Same as review |
| `inspect [server name]` | Same as review |
| `improve [server name]` | Same as review |
| `list reviews` | Shows pending code reviews |
| `show reviews` | Shows pending code reviews |
| `pending reviews` | Shows pending code reviews |
| `clear reviews` | Discards all pending reviews |
| `what can you review` | Lists all reviewable files |

**Reviewable files (say these after "review"):**
- `home assistant server` / `home assistant`
- `router` / `mcp router` / `router hub`
- `email server`
- `documents server` / `documents routes`
- `weather server`
- `internet server`
- `memory server` / `jsonl memory`
- `qnap server` / `qnap`
- `mikrotik server` / `mikrotik`
- `cognition` / `cognition server`
- `jarvis routes` / `routes`
- `app`
- `tts server`
- `stt server`
- `wake word`
- `ha config`

**Examples:**
- *"review the home assistant server"*
- *"analyze the router"*
- *"list reviews"*
- *"what can you review"*

> After a review, go to **http://YOUR-JARVIS-IP:5000/code_review**
> to see the suggestions and click **Approve & Write** or **Reject**.

---

## 💬 GENERAL CONVERSATION (Cognition)
If Jarvis doesn't match any of the above tools, your message goes to the LLM.
This handles general questions, math, writing help, brainstorming, etc.

| What to Say | What It Does |
|---|---|
| *Anything else* | Sent to LM Studio for AI response |

**Examples:**
- *"what is the capital of France"*
- *"write me a professional email to a client"*
- *"help me brainstorm ideas for my business"*
- *"how do I change a fuse in a breaker box"*

---

## 🗣️ TEXT-TO-SPEECH (Direct)
Force Jarvis to speak something directly.

| What to Say | What It Does |
|---|---|
| `speak [anything]` | Jarvis reads text aloud |
| `say [anything]` | Jarvis reads text aloud |

---

## 📝 NOTES
- Phrases are **not case-sensitive**
- You don't have to say them exactly — Jarvis matches keywords
- If Jarvis misroutes a command, the keyword list in `mcp_router_hub.py` can be updated
- All voice commands also work typed in the chat box
- You don't have to say them exactly — Jarvis matches keywords

---
*Jarvis 4.0 — Personal Neuro Layer — github.com/your-username/jarvis*
