"""
ICT Trading Bot Configuration
Contest: Top 100 | Contest 261118
Account: The5ers MetaTrader Contest
"""

# ═══════════════════════════════════════════════════════════════
# ACCOUNT SETTINGS
# ═══════════════════════════════════════════════════════════════
ACCOUNT_BALANCE = 10000.0       # Contest starting balance
MAX_LOSS_LIMIT = 1000.0         # Maximum total loss allowed
DAILY_LOSS_LIMIT = 500.0        # Maximum daily loss allowed

# ═══════════════════════════════════════════════════════════════
# RISK MANAGEMENT (Conservative for competition)
# ═══════════════════════════════════════════════════════════════
RISK_PER_TRADE_PCT = 1.0        # Risk 1% per trade ($100 on $10k)
MAX_OPEN_TRADES = 2             # Max simultaneous positions
MAX_TRADES_PER_DAY = 3          # Max trades per day (sniper approach)
MIN_RR_RATIO = 2.0              # Minimum Risk:Reward ratio

# ═══════════════════════════════════════════════════════════════
# PAIRS TO TRADE (Major pairs with best liquidity)
# ═══════════════════════════════════════════════════════════════
SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "XAUUSD",   # Majors + Gold
    "GBPJPY", "EURJPY", "USDCAD", "AUDUSD",    # Crosses
    "NAS100", "US30",                            # Indices
]

# ═══════════════════════════════════════════════════════════════
# ICT SESSION / KILL ZONE TIMES (UTC)
# ═══════════════════════════════════════════════════════════════
KILL_ZONES = {
    "asian": {"start": "00:00", "end": "08:00"},
    "london": {"start": "07:00", "end": "12:00"},     # London session
    "ny_am": {"start": "12:00", "end": "17:00"},       # NY AM Session
    "ny_pm": {"start": "17:00", "end": "22:00"},       # NY PM / Late session
}

# Active kill zones to trade in (all zones enabled for contest)
ACTIVE_KILL_ZONES = ["asian", "london", "ny_am", "ny_pm"]

# ═══════════════════════════════════════════════════════════════
# ICT STRATEGY PARAMETERS
# ═══════════════════════════════════════════════════════════════

# Fair Value Gap (FVG) detection
FVG_MIN_SIZE_PIPS = 3.0         # Minimum FVG size to consider
FVG_MAX_AGE_CANDLES = 50        # Max candle age for valid FVG

# Order Block detection
OB_LOOKBACK = 20                # Candles to look back for OB
OB_MIN_BODY_RATIO = 0.5        # Min body-to-wick ratio for valid OB

# Market Structure
MSS_LOOKBACK = 50               # Candles to look back for structure
SWING_LOOKBACK = 5              # Candles for swing high/low detection

# Liquidity levels
LIQ_EQUAL_THRESHOLD_PIPS = 3.0  # Pips tolerance for equal highs/lows

# ═══════════════════════════════════════════════════════════════
# TIMEFRAMES
# ═══════════════════════════════════════════════════════════════
HTF_TIMEFRAME = "H4"           # Higher timeframe for bias (4H)
LTF_TIMEFRAME = "M15"          # Lower timeframe for entry (15M)
ENTRY_TIMEFRAME = "M5"         # Entry precision timeframe (5M)

# ═══════════════════════════════════════════════════════════════
# SCAN INTERVAL
# ═══════════════════════════════════════════════════════════════
SCAN_INTERVAL_SECONDS = 30     # How often to scan for setups
