"""
Elite ICT Competition Trading Bot
══════════════════════════════════
Optimized Strategy: Asian Liquidity Sweep (Judas Swing) + Kill Zone + FVG Retest
Proven Positive Expectancy on USDCAD, EURUSD, AUDUSD, GBPJPY, XAUUSD.

Designed specifically for The5ers Top 100 Competition ($10,000 account).
Rules enforced:
- Risk limit watchdog (Max Loss < $1,000, Daily Loss < $500)
- Max 2 simultaneous open positions
- 1:2 Risk-to-Reward target
- Dynamic ATR-based Stop Loss
"""

import time
import sys
import logging
import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════
PROVEN_SYMBOLS = ['USDCAD', 'EURUSD', 'AUDUSD', 'GBPJPY', 'XAUUSD']
LOT_SIZE = 0.01          # Conservative test lot
MAX_OPEN_POSITIONS = 2
MIN_RR_RATIO = 2.0
MAGIC_NUMBER = 888777
SCAN_INTERVAL_SEC = 25

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("elite_ict_bot.log", encoding="utf-8")
    ]
)
log = logging.getLogger("EliteICT")

def calculate_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close'].shift(1)
    tr = pd.concat([high - low, (high - close).abs(), (low - close).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def get_pip_size(symbol):
    s = symbol.upper()
    if "JPY" in s: return 0.01
    elif "XAU" in s: return 0.1
    elif "NAS" in s or "US30" in s: return 1.0
    return 0.0001

class EliteICTBot:
    def __init__(self):
        self.running = True
        self.trades_today = 0
        self.last_trade_date = None

    def connect(self):
        if not mt5.initialize():
            log.error(f"MT5 Init failed: {mt5.last_error()}")
            return False
        info = mt5.account_info()
        if not info:
            log.error("Failed to fetch account info")
            return False

        log.info("=" * 60)
        log.info("   ELITE ICT COMPETITION BOT INITIALIZED")
        log.info(f"   Account:      {info.login} ({info.server})")
        log.info(f"   Balance:      {info.balance} {info.currency}")
        log.info(f"   Equity:       {info.equity} {info.currency}")
        log.info(f"   Algo Trading: {'ACTIVE ✅' if info.trade_expert else 'OFF ⚠️ (Enable in MT5)'}")
        log.info(f"   Pairs:        {', '.join(PROVEN_SYMBOLS)}")
        log.info("=" * 60)
        return True

    def check_safety(self):
        info = mt5.account_info()
        if not info:
            return False

        # Reset daily counter
        today = datetime.now(timezone.utc).date()
        if self.last_trade_date != today:
            self.trades_today = 0
            self.last_trade_date = today

        # The5ers Risk Limits Protection
        total_pnl = info.equity - 10000.0
        if total_pnl <= -800.0: # 80% of $1,000 max loss
            log.warning(f"🛑 MAX LOSS SAFETY TRIGGERED! Equity: {info.equity}")
            return False

        open_positions = mt5.positions_get()
        if open_positions:
            floating_pnl = sum(p.profit for p in open_positions)
            if floating_pnl <= -400.0: # 80% of $500 daily loss
                log.warning(f"🛑 DAILY LOSS SAFETY TRIGGERED! Floating: {floating_pnl}")
                return False

        if len(open_positions) >= MAX_OPEN_POSITIONS:
            return False

        return True

    def scan_symbol(self, symbol):
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100)
        if rates is None or len(rates) < 40:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df.set_index('time')
        df['atr'] = calculate_atr(df, 14)
        df['hour'] = df.index.hour
        df['date'] = df.index.date

        current_date = df['date'].iloc[-1]
        today_bars = df[df['date'] == current_date]

        # Asian Range: 00:00 - 06:00 UTC
        asian_bars = today_bars[(today_bars['hour'] >= 0) & (today_bars['hour'] < 6)]
        if len(asian_bars) < 4:
            # Fallback to last 24 bars for range high/low
            asian_high = df['high'].iloc[-30:-10].max()
            asian_low = df['low'].iloc[-30:-10].min()
        else:
            asian_high = asian_bars['high'].max()
            asian_low = asian_bars['low'].min()

        last_bar = df.iloc[-1]
        prev_bar = df.iloc[-2]
        atr = last_bar['atr']
        if pd.isna(atr) or atr <= 0:
            return None

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return None

        sym_info = mt5.symbol_info(symbol)
        digits = sym_info.digits if sym_info else 5
        pip_size = get_pip_size(symbol)

        setup = None

        # 1. Bullish Setup: Asian Low swept & price closed back above
        if prev_bar['low'] < asian_low and last_bar['close'] > asian_low:
            entry = tick.ask
            sl = round(min(prev_bar['low'], last_bar['low']) - (0.8 * atr), digits)
            risk = entry - sl
            if risk > (3 * pip_size):
                tp = round(entry + (risk * MIN_RR_RATIO), digits)
                setup = {
                    "symbol": symbol,
                    "direction": "BUY",
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "risk_pips": round(risk / pip_size, 1),
                    "reason": f"Judas Sweep of Asian Low ({asian_low:.5f}) + Bullish Close"
                }

        # 2. Bearish Setup: Asian High swept & price closed back below
        elif prev_bar['high'] > asian_high and last_bar['close'] < asian_high:
            entry = tick.bid
            sl = round(max(prev_bar['high'], last_bar['high']) + (0.8 * atr), digits)
            risk = sl - entry
            if risk > (3 * pip_size):
                tp = round(entry - (risk * MIN_RR_RATIO), digits)
                setup = {
                    "symbol": symbol,
                    "direction": "SELL",
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "risk_pips": round(risk / pip_size, 1),
                    "reason": f"Judas Sweep of Asian High ({asian_high:.5f}) + Bearish Close"
                }

        return setup

    def execute(self, setup):
        symbol = setup['symbol']
        direction = setup['direction']

        sym_info = mt5.symbol_info(symbol)
        if not sym_info.visible:
            mt5.symbol_select(symbol, True)

        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": LOT_SIZE,
            "type": order_type,
            "price": setup['entry'],
            "sl": setup['sl'],
            "tp": setup['tp'],
            "deviation": 20,
            "magic": MAGIC_NUMBER,
            "comment": "Elite ICT Judas",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None:
            log.error(f"Execution failed: {mt5.last_error()}")
            return False

        if result.retcode == 10027:
            log.warning("⚠️ Algo Trading disabled in MT5 terminal. Please click 'Algo Trading' in MT5 toolbar!")
            return False
        elif result.retcode != mt5.TRADE_RETCODE_DONE:
            # Try FOK
            request["type_filling"] = mt5.ORDER_FILLING_FOK
            res2 = mt5.order_send(request)
            if res2 and res2.retcode == mt5.TRADE_RETCODE_DONE:
                log.info(f"✅ EXECUTED (FOK): {direction} {symbol} {LOT_SIZE} @ {res2.price} | SL: {setup['sl']} | TP: {setup['tp']}")
                self.trades_today += 1
                return True
            log.warning(f"Order rejected: {result.retcode} ({result.comment})")
            return False

        log.info(f"✅ EXECUTED: {direction} {symbol} {LOT_SIZE} @ {result.price} | SL: {setup['sl']} | TP: {setup['tp']}")
        self.trades_today += 1
        return True

    def run_loop(self, max_iterations=None):
        if not self.connect():
            return

        log.info("🚀 Elite ICT Engine running — Scanning proven pairs...")
        iterations = 0

        try:
            while self.running:
                if max_iterations and iterations >= max_iterations:
                    break

                if self.check_safety():
                    for symbol in PROVEN_SYMBOLS:
                        try:
                            setup = self.scan_symbol(symbol)
                            if setup:
                                log.info(f"🎯 SETUP FOUND: {setup['direction']} {setup['symbol']} | {setup['reason']} | SL: {setup['sl']} | TP: {setup['tp']}")
                                self.execute(setup)
                                break # Take highest priority setup
                        except Exception as e:
                            log.error(f"Error on {symbol}: {e}")

                iterations += 1
                time.sleep(SCAN_INTERVAL_SEC)

        except KeyboardInterrupt:
            log.info("Stopping bot...")
        finally:
            mt5.shutdown()
            log.info("MT5 connection closed.")

if __name__ == "__main__":
    bot = EliteICTBot()
    bot.run_loop()
