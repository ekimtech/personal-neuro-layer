# Jarvis 4.0 — Trigger Phrases & Commands
*Last updated: 2026-03-20 — Phase 2 added*

---

## Memory
| What to say | What it does |
|---|---|
| `remember [anything]` | Saves a memory |
| `search memory for [topic]` | Searches your memory |
| `delete memory [ID]` | Deletes a memory entry |
| `list memory` | Lists all memories |

---

## Documents
| What to say | What it does |
|---|---|
| `create invoice` / `create an invoice` | Opens invoice form |
| `create estimate` / `new estimate` | Opens estimate form |
| `write a letter` / `create a letter` | Opens letter form |
| `create form` | Shows all three form links |
| `show my documents` / `list documents` | Opens document browser |

---

## Email
| What to say | What it does |
|---|---|
| `check my email` / `check email` | Reads inbox |
| `send email to [name]` | Compose and send |
| `how many emails` | Email count |
| `show inbox` / `list emails` | Lists emails |

---

## Home Assistant — Media
| What to say | What it does |
|---|---|
| `play [ARTIST] [ALBUM] on [SPEAKER]` | Plays music on Google Cast |
| `pause music` / `resume music` | Pause / resume playback |
| `stop music` | Stops playback |
| `next track` / `previous track` | Skip songs |
| `volume up` / `volume down` | Adjust volume |
| `set volume to [number]` | Set exact volume level |
| `what's playing` / `now playing` | Current song info |
| `list media players` | Lists all cast devices |
| `shuffle on` / `shuffle off` | Toggle shuffle |

## Home Assistant — Smart Home
| What to say | What it does |
|---|---|
| `turn on the [device]` | Turns on a device |
| `turn off the [device]` | Turns off a device |
| `dim the [light]` | Dims a light |
| `set thermostat to [temp]` | Sets temperature |
| `lock the door` / `unlock the door` | Lock control |
| `is the [device] on` | Check device state |
| `list all devices` | Shows all HA entities |

---

## Weather
| What to say | What it does |
|---|---|
| `weather in [city]` | Current weather |
| `forecast for [city]` | Weather forecast |
| `is it raining in [city]` | Rain check |
| `temperature in [city]` | Temperature only |

---

## Internet / Search
| What to say | What it does |
|---|---|
| `search for [topic]` | Web search |
| `latest news` / `headlines` | Top news stories |
| `look up [topic]` | Web lookup |
| `what's happening` | Current news |

---

## QNAP NAS
| What to say | What it does |
|---|---|
| `qnap status` | System overview |
| `qnap storage` | Disk / RAID status |
| `qnap logs` | Recent log entries |
| `list files [folder]` | Browse NAS files |
| `create folder [name]` | Make new folder |

---

## MikroTik Router
| What to say | What it does |
|---|---|
| `router status` | Router overview |
| `connected devices` / `who is on` | Devices on network |
| `block [IP address]` | Blacklist an IP |
| `unblock [IP address]` | Remove from blacklist |
| `firewall rules` | Show firewall rules |

---

## Security
| What to say | What it does |
|---|---|
| `security report` | Full report — blocked IPs, probes, recent events |
| `any threats today` | Same as full security report |
| `who tried to hack Jarvis` | Full security report |
| `jarvis security status` | Full security report |
| `show blocked IPs` / `banned IPs` | Lists all currently blocked IPs |
| `who is blocked` / `who is banned` | Lists blocked IPs |
| `blacklist` | Shows the blocked IP list |
| `show probe log` / `probe report` | Last 10 probe/scan attempts |
| `who probed` / `scan attempts` | Probe log summary |
| `failed login attempts` | All failed logins from security log |
| `brute force` | Failed login attempt report |
| `recent bans` / `who was banned` | IPs banned by the background scanner |
| `security log` / `show security` | Full security report |

---

## Crypto Wallet & Trading
| What to say | What it does |
|---|---|
| `wallet balance` / `how much ada` | Shows ADA balance |
| `wallet address` | Shows Jarvis's wallet address |
| `ada price` / `cardano price` | Current ADA/USD price |
| `trade signal` / `what would you trade` | Current EMA signal |
| `jarvis performance` / `trading performance` | Signal history summary |
| `phase 2 status` / `is jarvis trading` | Live trading on/off status |
| `approve trade` / `confirm trade` | Approve pending real trade |
| `reject trade` / `cancel trade` | Reject pending real trade |
| `transaction history` | Recent wallet transactions |
| `trade performance` | see all trades |
Jarvis now responds to:

"how are my trades doing"
"paper trading performance"
"paper results"
Returns win rate, P&L, open trades list, last 5 closed with
---

## Self-Writing Tools
| What to say | What it does |
|---|---|
| `review [filename]` | AI reviews that file |
| `analyze [filename]` | Same as review |
| `list reviews` | Pending reviews |
| `clear reviews` | Dismiss all reviews |
| `what can you review` | Lists available files |

---

## Miss Log (Self-Improvement)
| What to say | What it does |
|---|---|
| `miss log` | Shows all unhandled request patterns |
| `what did you miss` | Same as miss log |
| `miss summary` / `miss report` | Summary of top unrecognized topics |
| `what are you missing` | Shows capability gaps |
| `unhandled requests` | Full miss log |

---

## General (Jarvis AI)
Anything not matching the above goes directly to Qwen via LM Studio — general questions, conversation, advice, and anything else.

---
"Play Josh Groban" → plays everything by Josh Groban
"Play Live at the Greek by Josh Groban" → plays that specific album
"Play Josh Groban's Live at the Greek" → same thing
"Play Metallica" → plays everything by Metallica
"Play The Black Album by Metallica" → that album specifically
"Play Frank Sinatra" → any Frank Sinatra you have
*Tip: Triggers are not case-sensitive. You can speak or type them.*
