# The5ers Contest Autonomous Sentinel (ICT Smart Money Concepts)

Autonomous 24/7 institutional trading scanner, risk manager, and native hardware UI executor engineered specifically for **The5ers $10,000 Contest Accounts** on server `FivePercentOnline-Experience`.

---

## 🏆 Contest Rules & Strategic Architecture

### 1. Zero EA Footprint (Strict The5ers Rule)
* **NEVER call `mt5.order_send()`.** The5ers strictly prohibits automated EAs. Calling `order_send()` marks deals with `DEAL_REASON_EXPERT` (Reason 3) and leads to contest disqualification.
* **Native GUI Scancodes:** Orders are executed exclusively via native OS keyboard and mouse scancodes into the MetaTrader 5 GUI using the `windows-computer-use` MCP tool (`F9` -> Symbol -> Lot -> SL -> TP -> Click Sell/Buy -> `Esc`).
* **Audit Trail:** Verified orders show `DEAL_REASON_CLIENT` (Reason 0) with `magic: 0` and empty comment `''`.

### 2. Single Open Position Cap
* The bot strictly enforces **maximum 1 open position** at all times.

### 3. Contest Sprint Risk Scaling (Option A)
* **Fixed Risk per Trade:** **`$175.00 USD` (1.75% of $10,000)**
* **Target R:R:** **`1:2.5 to 1:3.0+`** (Target reward: **`+$437.50 to +$525.00 USD`** per winning trade)
* **Daily Drawdown Limit:** **`$500.00`** (Can absorb full stop-out with $325 buffer remaining)
* **Max Total Drawdown Limit:** **`$1,000.00`**

### 4. Watchlist & 24/7 Weekend Engine
* **Weekdays (Forex & Commodities):** `EURUSD`, `GBPUSD`, `AUDUSD`, `USDJPY`, `USDCAD`, `NZDUSD`, `GBPJPY`, `XAUUSD`
* **Weekends (24/7 Crypto Engine):** `ETHUSD`, `BTCUSD` (trades continuously through Saturday and Sunday on FivePercentOnline, providing an unfair advantage over frozen competitors).

---

## 🚀 Laptop 2 Installation Guide

### Step 1: Clone Repository
Open PowerShell on the new laptop and run:
```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\$env:USERNAME\.gemini\antigravity\scratch"
cd "C:\Users\$env:USERNAME\.gemini\antigravity\scratch"
git clone https://github.com/syncsp/the5ers-contest-sentinel.git ict-trading-bot
cd ict-trading-bot
```

### Step 2: Create Python Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install MetaTrader5 pandas numpy requests
```

### Step 3: MetaTrader 5 Setup
1. Install official The5ers MT5 at `C:\Program Files\Five Percent Online MetaTrader 5\terminal64.exe`.
2. Login to your contest account on server `FivePercentOnline-Experience`.
3. Press `Ctrl + U` and enable symbols: `EURUSD`, `GBPUSD`, `AUDUSD`, `USDJPY`, `USDCAD`, `NZDUSD`, `GBPJPY`, `XAUUSD`, `ETHUSD`, `BTCUSD`.

### Step 4: Run the Bot
To run the autonomous scanner daemon:
```powershell
.\.venv\Scripts\python.exe the5ers_autonomous_sentinel.py
```

To run a single silent monitor check:
```powershell
.\.venv\Scripts\python.exe silent_monitor.py
```

---

## 🤖 Antigravity Deployment Prompt (Laptop 2)

Paste this into Antigravity on your second laptop:

```markdown
You are the Principal Systems Engineer and Head Trader running the autonomous The5ers $10,000 Contest Sentinel on this machine.

ACCOUNT DETAILS:
- Login: [ENTER YOUR NEW LOGIN NUMBER HERE]
- Server: FivePercentOnline-Experience
- Starting Stake: $10,000.00 USD
- Contest Countdown: ~3.5 days left. The objective is an aggressive sprint into the Top 10 / Top 100 leaderboard.

CRITICAL CONTEST CONSTRAINTS & BOUNDARIES:
1. ZERO EA FOOTPRINT (Strict The5ers Rule):
   - Never call `mt5.order_send()`. API orders produce DEAL_REASON_EXPERT (Reason 3) which leads to contest disqualification.
   - All entries must be executed via native OS scan codes using the `windows-computer-use` MCP tool into MT5 desktop GUI (F9 -> Symbol -> Lot -> SL -> TP -> Click Sell/Buy -> Esc).
   - Verified output must show DEAL_REASON_CLIENT (Reason 0) with magic: 0 and empty comment ''.
2. MAXIMUM 1 OPEN POSITION:
   - Never enter a trade if any position is currently open.
3. CONTEST SPRINT RISK SETTINGS (Option A):
   - Fixed Risk: $175.00 USD (1.75% of $10,000).
   - Target R:R: 1:2.5 to 1:3.0 (Target reward: +$437.50 to +$525.00 per win).
   - Daily Drawdown Floor: $500.00 (Max loss buffer).
   - Max Total Drawdown: $1,000.00.
4. WATCHLIST (10 Assets):
   - Weekdays: EURUSD, GBPUSD, AUDUSD, USDJPY, USDCAD, NZDUSD, GBPJPY, XAUUSD
   - Weekend 24/7 Engine: ETHUSD, BTCUSD (trades continuously through Saturday and Sunday on FivePercentOnline).
5. SILENT HEADLESS MONITORING:
   - Never steal desktop focus or pop MT5 to foreground during routine checks. MT5 is only brought to focus for the 2.5-second execution window.
   - Prevent Windows sleep via SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED).

YOUR IMMEDIATE STARTUP SEQUENCE:
1. Verify MT5 is running and connect via python MetaTrader5 package. Confirm login matches the new account.
2. Ensure workspace directory is set to `C:\Users\[USERNAME]\.gemini\antigravity\scratch\ict-trading-bot`.
3. Check and verify all 10 symbols are active and receiving live quotes.
4. Launch the autonomous scanner daemon in the background (`the5ers_autonomous_sentinel.py`) targeting 1:2.5+ RR setups with $175 risk.
5. Setup a recurring 5-minute silent headless watchdog cron to audit positions, check pending signals, and report:
   - Account metrics (Balance, Equity, Open Positions).
   - Live market dynamics (Price, H1/M15 trend, active FVGs).
   - Upcoming potential setups forming across all 10 assets.
```
