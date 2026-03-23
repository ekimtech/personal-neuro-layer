# Jarvis — Personal Neuro Layer

A fully working personal AI assistant you can run in your own home today.

While enterprise AI frameworks are blueprints, **Personal Neuro Layer** is a complete, running system built for real daily life — home automation, email, crypto trading, security monitoring, documents, memory, and voice control, all connected through a single intelligent routing layer.

---

## What It Does

| Module | Capability |
|--------|-----------|
| 🧠 **Neuro Layer** | Central router — classifies intent and dispatches to the right organ |
| 💬 **LLM (Local)** | Powered by any LM Studio model (default: Qwen 2.5 14B) |
| 🏠 **Home Assistant** | Lights, switches, media, climate, scenes, sensors |
| 🎵 **Music** | Play any artist or album via Music Assistant |
| 📧 **Email** | Read, search, compose, send via IMAP/SMTP |
| 📄 **Documents** | Generate invoices, estimates, and letters as PDF |
| 📇 **Contacts** | Full contact management |
| 🔐 **Security** | Login protection, IP blacklisting, auto-ban via MikroTik SSH |
| 🌐 **Network** | MikroTik router stats, VPN, connected devices |
| 💾 **NAS** | QNAP storage management |
| 💰 **Crypto** | ADA paper + live trading, EMA crossover signals, Blockfrost wallet |
| 🌤️ **Weather** | Current conditions + forecast (Open-Meteo, no API key needed) |
| 🔍 **Web Search** | DuckDuckGo search + page fetch |
| 📰 **News** | Latest headlines |
| 🧠 **Memory** | Long-term JSONL memory + vector DB semantic search |
| 🎙️ **Voice** | Wake word listener + Tap to Talk (browser mic via HTTPS) |
| 🤖 **Self-Review** | Jarvis can review and suggest improvements to his own code |

---

## Architecture

```
User Input (text or voice)
        ↓
   mcp_router_hub.py          ← The Neuro Layer (central brain)
        ↓
 Intent Classification
        ↓
┌──────────────────────────────────────────┐
│  LLM  │ Memory │ Home Assistant │ Email  │
│ Crypto │ Network │ Weather │ Search │ NAS │
└──────────────────────────────────────────┘
        ↓
   Response → TTS → Audio
```

Each organ is isolated — add, remove, or swap any module without touching the others.

---

## Requirements

- **Python 3.10+**
- **Windows** (Linux/Mac support in progress)
- **LM Studio** — [Download here](https://lmstudio.ai) — run any local LLM
- **Home Assistant** (optional) — for smart home control
- **MikroTik router** (optional) — for network monitoring and security
- **QNAP NAS** (optional) — for storage management
- **Blockfrost account** (optional) — for crypto wallet features

### Hardware Requirements for Local AI

Jarvis runs its AI brain locally through LM Studio — performance depends on your hardware.

| Spec | Minimum | Recommended |
|------|---------|-------------|
| RAM | 16GB | 32GB |
| GPU VRAM | 6GB | 8GB+ |
| CPU | 6-core modern | 8-core+ |
| Storage | 20GB free | 40GB+ free |

The default model is **Qwen2.5-14B** — a strong balance of intelligence and speed on mid-range hardware.

If your machine struggles, swap to a smaller **7B model** in LM Studio with no other changes required. The model name can be updated in `model_injection/cognition.py`.

> **No GPU?** CPU-only mode works but responses will be slow. A 7B model on a modern CPU is usable for light tasks.

---

## Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/your-username/jarvis.git
cd jarvis
```

### 2. Run setup
```bash
setup.bat
```

### 3. Configure your settings

Edit the config files created during setup:

**Required:**
- `mcp_servers_hub/login_security/auth_config.py` — set your login username + password

**Optional (enables each module):**
- `mcp_servers_hub/home_assistant_server/ha_config.py` — Home Assistant IP + token
- `mcp_servers_hub/email_server/.env` — email credentials
- `mcp_servers_hub/mikrotik_server/mikrotik_config.py` — router IP + credentials
- `mcp_servers_hub/qnap_server/qnap_config.py` — NAS IP + token
- `mcp_servers_hub/crypto_wallet_server/wallet_config.py` — Blockfrost project ID

Set your default weather location in `mcp_servers_hub/internet_server/server.py`:
```python
DEFAULT_LOCATION = "Your City, ST"
```

### 4. Start LM Studio
- Download and install [LM Studio](https://lmstudio.ai)
- Load a model (recommended: `qwen2.5-14b-instruct`)
- Start the local server on port `1234`

### 5. Start Jarvis
```bash
python app.py
```

### 6. Open in browser
```
http://localhost:5000
```

Log in with the credentials you set in `auth_config.py`.

---

## Mobile Access

To access Jarvis from your phone on your local network:

1. Find your PC's local IP address (e.g. `192.168.1.100`)
2. Open `http://192.168.1.100:5000` in your phone's browser

For HTTPS (required for microphone access on mobile):
- Use a [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) to expose Jarvis securely over HTTPS
- Or run `python generate_cert.py` to create a self-signed certificate for LAN use

---

## Voice Control

**Wake Word (PC):** Say "Hey Jarvis" — the PC microphone listens continuously when Jarvis is running.

**Tap to Talk (Browser):** Click the microphone button on the chat page — works on any device with a microphone over HTTPS.

---

## Memory System

Jarvis remembers things you tell him using a two-layer memory system:
- **JSONL Memory** — structured entries for facts, contacts, dates, preferences
- **Vector DB** — semantic search for natural language recall

Tell him anything:
> *"Remember that my wife's birthday is March 15"*
> *"Note that I prefer dark roast coffee"*

He'll recall it in future conversations.

---

## Crypto Trading

The trading module runs **paper trades** (simulated) in parallel with **live trades** at all times.

- EMA 5/20 crossover signals on 15-minute ADA candles
- Every live trade requires manual approval before execution
- Paper trading tracks performance silently — evaluate signals before going live
- Powered by [Blockfrost](https://blockfrost.io) + Minswap DEX

---

## Project Structure

```
jarvis/
├── app.py                          # Flask boot layer
├── jarvis_routes.py                # Web routes (chat, voice, pages)
├── model_injection/
│   ├── cognition.py                # LLM call + memory injection
│   └── prompts.py                  # System prompt + context builder
├── mcp_servers_hub/
│   ├── mcp_router_hub.py           # The Neuro Layer — central router
│   ├── home_assistant_server/      # Smart home organ
│   ├── email_server/               # Email organ
│   ├── crypto_wallet_server/       # Crypto trading organ
│   ├── mikrotik_server/            # Router organ
│   ├── qnap_server/                # NAS organ
│   ├── internet_server/            # Weather, search, news
│   ├── login_security/             # Auth + security scanner
│   ├── stt_server/                 # Speech-to-text + wake word
│   ├── self_writing_server/        # Code review organ
│   └── memory_servers/             # JSONL + vector DB memory
├── templates/                      # HTML UI pages
├── static/                         # CSS, JS, images
└── setup.bat                       # Windows setup script
```

---

## Roadmap

- [ ] React Native mobile app (iOS + Android)
- [ ] Google Tools organ (Calendar, Drive, Docs)
- [ ] Son's electrical business portal
- [ ] Linux/Mac setup script
- [ ] Docker container

---

## License

MIT License — free to use, modify, and distribute.

---

*Built with purpose. Engineered by [Ekimtech.com](https://ekimtech.com)*
