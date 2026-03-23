# Jarvis 4.0 — Trading Brain Phase 2 Roadmap
*Created: 2026-03-19 | Target: ~1 week after Phase 1 paper trading*

---

## Phase 1 Status (Current)
- [x] Wallet generated — (your wallet address will appear in `wallet.seed` after first run)
- [x] Funded with 100 ADA
- [x] Paper trading live — signals logged, no real execution
- [x] EMA 5/20 crossover strategy running
- [x] Crypto dashboard at `/crypto`
- [x] Signal history table (last 200 entries)
- [ ] Accumulating learning data — let run for 1 week before Phase 2

---

## Phase 2 Build List

### 1. Switch to 15-Minute Candles
- **Why:** 2-minute sampling catches too much noise (saw BUY→SELL flip in 10 min that would have been a losing trade)
- **What changes:**
  - `trading_brain.py` — change price sample scheduler to every 15 minutes
  - `price_history.json` — increase max stored points from 50 → 100+ (data comes in slower)
  - Crypto dashboard auto-refresh — change from 2 min → 15 min
- **Effect:** EMA Short (5) = 75 min coverage, EMA Long (20) = 5 hours coverage — much stronger signals

---

### 2. Win/Loss Trade Outcome Tracker
- **Why:** Current performance summary only counts BUY/SELL/HOLD totals — doesn't show if trades were profitable
- **What to build:**
  - When a BUY signal is followed by a SELL, record a completed trade:
    - Entry price (price at first BUY)
    - Exit price (price at first SELL)
    - Profit/loss % and dollar amount
    - Hold duration (how long between BUY and SELL)
    - Win or loss
  - Store in `completed_trades.json`
  - Add win rate % to performance dashboard card
  - Add trade history table to `/crypto` dashboard

---

### 3. Actual DEX Trade Execution via Minswap
- **Why:** Phase 1 is paper only — Phase 2 puts real ADA to work
- **What to build:**
  - Minswap DEX integration for ADA swaps
  - Trade size: 5 ADA per signal (tight, controlled)
  - Stop loss: 3% (already configured)
  - Take profit: 5% (already configured)
  - Only execute on confirmed EMA crossover signals (not ACCUMULATING)
  - Dry-run mode toggle — ability to flip back to paper trading instantly

---

### 4. EMA Period Tuning (Data Driven)
- **Why:** 5/20 was a starting point — real data will show if it needs adjustment
- **Plan:**
  - After 1 week of 15-min candle data, review win/loss ratio
  - If win rate < 50%, experiment with 10/50 EMA periods
  - Consider RSI (Relative Strength Index) as a secondary confirmation filter
  - Only change one variable at a time, compare results

---

### 5. Risk Controls
- **Daily loss limit** — if paper/real trades lose more than X% in a day, pause trading
- **Max open positions** — never have more than 1 trade open at a time (Phase 2)
- **Minimum signal confidence** — require EMA gap to exceed a threshold before triggering (filters weak crossovers)
- **Cooldown period** — after a losing trade, wait at least 1 candle before re-entering

---

### 6. Dashboard Improvements
- Add win rate % to Performance card
- Add completed trades table (entry, exit, P&L, duration)
- Add a simple equity curve chart (wallet value over time)
- Color-code P&L — green positive, red negative
- Add 15-min candle indicator so it's clear what timeframe is active

---

### 7. Offline / No Internet Handling
- **Why:** When internet drops, Blockfrost and CoinGecko calls fail silently — dashboard shows blank cards which looks like a bug
- **What to build:**
  - Detect connection failure in API error handlers
  - Show `⚠️ No internet connection` banner on crypto dashboard when external APIs are unreachable
  - All local Jarvis features (chat, Home Assistant, memory, documents) continue working normally
  - Flask will never crash — all external calls already wrapped in `try/except` with `timeout=10`
  - Banner auto-clears on next successful refresh when internet is restored

---

### 8. Whisper STT Model Pre-Cache (Install Guide Item)
- **Why:** Whisper downloads the ~141MB "small" model from HuggingFace on first run — if internet is down on first startup, STT/voice crashes
- **Fix:** One-time command to pre-download and cache the model while internet is available:
  ```bash
  python -c "import whisper; whisper.load_model('small')"
  ```
- **After that:** Model is cached locally at `~/.cache/whisper/` and never needs internet again
- **Add to:** Final install guide / setup instructions so new installs always run this step
- **Voice/STT is fully offline after first cache** — no ongoing internet dependency

---

## Notes from Paper Trading Observations (2026-03-19)
- At 2-min sampling, saw a BUY→SELL flip in 10 minutes
- Entry ~$0.2662, exit ~$0.2652 = **−0.38% loss** — pure EMA lag
- At 15-min candles this trade would have never triggered
- ADA was in downtrend from ~15:21 onward, consistent SELL signals
- EMA gap widened then slowly narrowed — downtrend losing steam toward end of session
- System is reading the market correctly, just needs coarser candles

---

## Phase 3 (Future — No Timeline Yet)
- Google Sheets integration for son's electrical business
- Potential multi-asset tracking (not just ADA)
- Automated portfolio rebalancing alerts
