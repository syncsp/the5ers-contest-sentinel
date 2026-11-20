"""
FTMO Turbo Scalper (High-Velocity M1/M5 Execution)
══════════════════════════════════════════════════
Optimized for FTMO $10,000 Challenge Rules:
- Lot Size: 0.30 lots for Forex (~$18 risk per scalp)
            0.10 lots for Gold (~$15 risk per scalp)
- Fast M1 Entry: ICT FVG + Liquidity Sweep + Order Block Bounce
- Auto-Breakeven at +3.5 pips (Risk-Free Mode)
- Trailing Stop: 3.5 pips dynamic lock
- Max 2 concurrent positions (Respects FTMO position ceiling)
- Daily Hard Stop: $350 (Well below FTMO $500 max daily loss)
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
FOREX_SYMBOLS = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD']
GOLD_SYMBOL = 'XAUUSD'

FOREX_LOT = 0.30       # Good aggressive scalp lot as requested
GOLD_LOT = 0.10        # Adjusted for Gold pip value

MAX_POSITIONS = 2      # FTMO Demo position ceiling
SCAN_INTERVAL_SEC = 5  # High-frequency 5s scan
MAGIC_NUMBER = 999111

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("turbo_scalp.log", encoding="utf-8")
    ]
)
log = logging.getLogger("TurboScalper")

def get_pip_size(symbol):
    s = symbol.upper()
    if "JPY" in s: return 0.01
    elif "XAU" in s: return 0.1
    return 0.0001

class FTMOTurboScalper:
    def __init__(self):
        self.running = True
        self.daily_start_balance = 10000.0

    def connect(self):
        if not mt5.initialize():
            log.error(f"MT5 Init Failed: {mt5.last_error()}")
            return False
        info = mt5.account_info()
        if not info:
            log.error("Failed to read account info")
            return False

        self.daily_start_balance = info.balance
        log.info("=" * 65)
        log.info("   ⚡ FTMO TURBO SCALPER INITIALIZED (FAST M1 EXECUTION) ⚡")
        log.info(f"   Account:        {info.login} ({info.server})")
        log.info(f"   Balance:        {info.balance:.2f} {info.currency}")
        log.info(f"   Forex Lot:      {FOREX_LOT} (~$18 risk / +$36 target per trade)")
        log.info(f"   Gold Lot:       {GOLD_LOT} (~$15 risk / +$30 target per trade)")
        log.info(f"   Scan Speed:     Every {SCAN_INTERVAL_SEC}s (Fast Tick Mode)")
        log.info("=" * 65)
        return True

    def check_safety_watchdog(self):
        """Enforces FTMO Max Daily Loss & Max Overall Loss safety."""
        info = mt5.account_info()
        if not info: return False

        # FTMO Daily Loss Watchdog: Max $350 (Buffer under $500)
        daily_loss = self.daily_start_balance - info.equity
        if daily_loss >= 350.0:
            log.warning(f"🛑 FTMO SAFETY STOP: Daily loss hit ${daily_loss:.2f}! Pausing.")
            return False

        # FTMO Max Loss Watchdog: Max $750 (Buffer under $1,000)
        total_loss = 10000.0 - info.equity
        if total_loss >= 750.0:
            log.warning(f"🛑 FTMO OVERALL SAFETY STOP: Equity dropped to ${info.equity:.2f}! Pausing.")
            return False

        return True

    def manage_active_scalps(self):
        """Auto-Breakeven at +3.5 pips & Dynamic Trailing Stop."""
        positions = mt5.positions_get()
        if not positions:
            return 0

        for p in positions:
            pip_size = get_pip_size(p.symbol)
            is_buy = (p.type == 0)
            digits = mt5.symbol_info(p.symbol).digits
            profit_pips = ((p.price_current - p.price_open) if is_buy else (p.price_open - p.price_current)) / pip_size

            # 1. Auto-Breakeven at +3.5 pips profit
            if profit_pips >= 3.5:
                at_be = (p.sl >= p.price_open) if is_buy else (p.sl <= p.price_open and p.sl > 0)
                if not at_be:
                    be_sl = round(p.price_open + (0.5 * pip_size if is_buy else -0.5 * pip_size), digits)
                    req = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": p.ticket,
                        "symbol": p.symbol,
                        "sl": be_sl,
                        "tp": p.tp,
                    }
                    res = mt5.order_send(req)
                    if res and (res.retcode == mt5.TRADE_RETCODE_DONE or res.retcode == 10009):
                        log.info(f"🔒 BREAKEVEN LOCKED: #{p.ticket} {p.symbol} SL moved to {be_sl} (+{profit_pips:.1f} pips)")

            # 2. Dynamic Trailing Stop at +6 pips profit (trails by 3.5 pips)
            if profit_pips >= 6.0:
                trail_sl = round(p.price_current - (3.5 * pip_size if is_buy else -3.5 * pip_size), digits)
                should_trail = (trail_sl > p.sl) if is_buy else (trail_sl < p.sl or p.sl == 0)
                if should_trail:
                    req = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": p.ticket,
                        "symbol": p.symbol,
                        "sl": trail_sl,
                        "tp": p.tp,
                    }
                    mt5.order_send(req)

        return len(positions)

    def scan_m1_fast_signal(self, symbol):
        """Scans for rapid M1 price action entries."""
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 45)
        if rates is None or len(rates) < 25:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df.set_index('time')

        pip_size = get_pip_size(symbol)
        digits = mt5.symbol_info(symbol).digits
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return None

        df['ema7'] = df['close'].ewm(span=7, adjust=False).mean()
        df['ema14'] = df['close'].ewm(span=14, adjust=False).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3]

        recent_high = df['high'].iloc[-18:-2].max()
        recent_low = df['low'].iloc[-18:-2].min()

        lot = GOLD_LOT if symbol == GOLD_SYMBOL else FOREX_LOT

        # ── Setup 1: Micro Liquidity Sweep & Rejection ──
        if prev['low'] < recent_low and last['close'] > recent_low and last['close'] > last['open']:
            entry = tick.ask
            sl_pips = 5.0 if symbol != GOLD_SYMBOL else 15.0
            tp_pips = sl_pips * 2.0
            return {
                "symbol": symbol,
                "direction": "BUY",
                "volume": lot,
                "entry": entry,
                "sl": round(entry - (sl_pips * pip_size), digits),
                "tp": round(entry + (tp_pips * pip_size), digits),
                "strategy": "M1 Liq Sweep",
                "expected_profit": f"+${tp_pips * (10 if symbol != GOLD_SYMBOL else 1) * lot:.1f}"
            }

        elif prev['high'] > recent_high and last['close'] < recent_high and last['close'] < last['open']:
            entry = tick.bid
            sl_pips = 5.0 if symbol != GOLD_SYMBOL else 15.0
            tp_pips = sl_pips * 2.0
            return {
                "symbol": symbol,
                "direction": "SELL",
                "volume": lot,
                "entry": entry,
                "sl": round(entry + (sl_pips * pip_size), digits),
                "tp": round(entry - (tp_pips * pip_size), digits),
                "strategy": "M1 Liq Sweep",
                "expected_profit": f"+${tp_pips * (10 if symbol != GOLD_SYMBOL else 1) * lot:.1f}"
            }

        # ── Setup 2: ICT M1 Fair Value Gap Burst ──
        if last['low'] > prev2['high'] and (last['low'] - prev2['high']) >= (1.2 * pip_size):
            entry = tick.ask
            sl_pips = 5.0 if symbol != GOLD_SYMBOL else 15.0
            tp_pips = sl_pips * 2.0
            return {
                "symbol": symbol,
                "direction": "BUY",
                "volume": lot,
                "entry": entry,
                "sl": round(entry - (sl_pips * pip_size), digits),
                "tp": round(entry + (tp_pips * pip_size), digits),
                "strategy": "M1 FVG Scalp",
                "expected_profit": f"+${tp_pips * (10 if symbol != GOLD_SYMBOL else 1) * lot:.1f}"
            }

        elif last['high'] < prev2['low'] and (prev2['low'] - last['high']) >= (1.2 * pip_size):
            entry = tick.bid
            sl_pips = 5.0 if symbol != GOLD_SYMBOL else 15.0
            tp_pips = sl_pips * 2.0
            return {
                "symbol": symbol,
                "direction": "SELL",
                "volume": lot,
                "entry": entry,
                "sl": round(entry + (sl_pips * pip_size), digits),
                "tp": round(entry - (tp_pips * pip_size), digits),
                "strategy": "M1 FVG Scalp",
                "expected_profit": f"+${tp_pips * (10 if symbol != GOLD_SYMBOL else 1) * lot:.1f}"
            }

        # ── Setup 3: Fast Micro Momentum Pulse (EMA 7/14 cross) ──
        if prev['ema7'] <= prev['ema14'] and last['ema7'] > last['ema14'] and last['close'] > last['open']:
            entry = tick.ask
            sl_pips = 5.0 if symbol != GOLD_SYMBOL else 15.0
            tp_pips = sl_pips * 1.8
            return {
                "symbol": symbol,
                "direction": "BUY",
                "volume": lot,
                "entry": entry,
                "sl": round(entry - (sl_pips * pip_size), digits),
                "tp": round(entry + (tp_pips * pip_size), digits),
                "strategy": "M1 Micro Momentum",
                "expected_profit": f"+${tp_pips * (10 if symbol != GOLD_SYMBOL else 1) * lot:.1f}"
            }

        elif prev['ema7'] >= prev['ema14'] and last['ema7'] < last['ema14'] and last['close'] < last['open']:
            entry = tick.bid
            sl_pips = 5.0 if symbol != GOLD_SYMBOL else 15.0
            tp_pips = sl_pips * 1.8
            return {
                "symbol": symbol,
                "direction": "SELL",
                "volume": lot,
                "entry": entry,
                "sl": round(entry + (sl_pips * pip_size), digits),
                "tp": round(entry - (tp_pips * pip_size), digits),
                "strategy": "M1 Micro Momentum",
                "expected_profit": f"+${tp_pips * (10 if symbol != GOLD_SYMBOL else 1) * lot:.1f}"
            }

        return None

    def execute_turbo(self, s):
        symbol = s['symbol']
        direction = s['direction']

        sym_info = mt5.symbol_info(symbol)
        if not sym_info.visible:
            mt5.symbol_select(symbol, True)

        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL

        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": s['volume'],
            "type": order_type,
            "price": s['entry'],
            "sl": s['sl'],
            "tp": s['tp'],
            "deviation": 10,
            "magic": MAGIC_NUMBER,
            "comment": f"{s['strategy'][:10]}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        res = mt5.order_send(req)
        if res and (res.retcode == mt5.TRADE_RETCODE_DONE or res.retcode == 10009):
            log.info(f"⚡ TURBO SCALP EXECUTED: [{s['strategy']}] {direction} {symbol} {s['volume']} lot | SL: {s['sl']} | TP: {s['tp']} (Target: {s['expected_profit']})")
            return True
        else:
            req["type_filling"] = mt5.ORDER_FILLING_FOK
            res2 = mt5.order_send(req)
            if res2 and (res2.retcode == mt5.TRADE_RETCODE_DONE or res2.retcode == 10009):
                log.info(f"⚡ TURBO SCALP EXECUTED (FOK): [{s['strategy']}] {direction} {symbol} {s['volume']} lot | SL: {s['sl']} | TP: {s['tp']}")
                return True
            log.warning(f"Order skipped: {res.retcode if res else 'None'} ({res.comment if res else ''})")
            return False

    def run(self):
        if not self.connect():
            return

        all_symbols = FOREX_SYMBOLS + [GOLD_SYMBOL]
        log.info(f"🚀 TURBO SCALPER RUNNING — High Frequency Mode Active across {len(all_symbols)} pairs...")

        try:
            while self.running:
                if not self.check_safety_watchdog():
                    time.sleep(30)
                    continue

                active_count = self.manage_active_scalps()

                if active_count < MAX_POSITIONS:
                    open_syms = [p.symbol for p in (mt5.positions_get() or [])]
                    for s in all_symbols:
                        if s in open_syms:
                            continue

                        sig = self.scan_m1_fast_signal(s)
                        if sig:
                            log.info(f"🔥 FAST TRIGGER: {sig['strategy']} on {sig['symbol']} {sig['direction']}")
                            if self.execute_turbo(sig):
                                break # 1 order per cycle

                time.sleep(SCAN_INTERVAL_SEC)

        except KeyboardInterrupt:
            log.info("Turbo Scalper stopped.")
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    scalper = FTMOTurboScalper()
    scalper.run()
