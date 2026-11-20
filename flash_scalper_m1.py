"""
FTMO 1-Minute Flash Scalper (High-Frequency Micro-Exit Engine)
══════════════════════════════════════════════════════════════
- Max Trade Hold Time: 45 to 60 seconds (1 minute max!)
- Quick Profit Snatch: Auto-banks profit at +1.5 to +2.5 pips (+10 to +$15 USD)
- Time-Out Exit: Closes stalled positions at 60s to free capital
- Continuous Hunting: Instantly scans & fires next setup within 1 second
- Aggressive Lot: 0.50 lot Forex / 0.15 lot Gold
"""

import time
import sys
import logging
import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════
SYMBOLS = ['EURUSD', 'GBPUSD', 'AUDUSD', 'USDJPY', 'XAUUSD']
LOT_FOREX = 0.50          # Aggressive fast scalp size
LOT_GOLD = 0.15

MAX_HOLD_SECONDS = 60     # 1-minute hard exit rule
PROFIT_SNATCH_PIPS = 2.0  # Immediate bank at +2 pips
HARD_SL_PIPS = 6.0        # Emergency cap
MAX_OPEN_POSITIONS = 2
MAGIC_NUMBER = 777111

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("flash_scalp.log", encoding="utf-8")
    ]
)
log = logging.getLogger("FlashScalp")

def get_pip(symbol):
    s = symbol.upper()
    if "JPY" in s: return 0.01
    elif "XAU" in s: return 0.1
    return 0.0001

class FlashScalper:
    def __init__(self):
        self.running = True
        self.trade_entry_times = {} # ticket -> timestamp

    def connect(self):
        if not mt5.initialize():
            log.error(f"MT5 Init Error: {mt5.last_error()}")
            return False
        info = mt5.account_info()
        log.info("=" * 65)
        log.info("   ⚡ 1-MINUTE FLASH SCALPER ACTIVATED (NO LONG WAITING) ⚡")
        log.info(f"   Account:        {info.login} ({info.server})")
        log.info(f"   Balance:        ${info.balance:.2f} USD")
        log.info(f"   Lot Size:       {LOT_FOREX} Lots Forex / {LOT_GOLD} Gold")
        log.info(f"   Max Hold Time:  {MAX_HOLD_SECONDS}s (Rapid In-and-Out)")
        log.info(f"   Profit Target:  +{PROFIT_SNATCH_PIPS} pips (+${PROFIT_SNATCH_PIPS * 10 * LOT_FOREX:.1f} per scalp)")
        log.info("=" * 65)
        return True

    def manage_flash_exits(self):
        """Active 1-minute exit manager: snatches profit & cuts stalls."""
        positions = mt5.positions_get()
        if not positions:
            return 0

        now = time.time()

        for p in positions:
            pip_size = get_pip(p.symbol)
            is_buy = (p.type == 0)
            profit_pips = ((p.price_current - p.price_open) if is_buy else (p.price_open - p.price_current)) / pip_size

            # Track trade duration
            if p.ticket not in self.trade_entry_times:
                self.trade_entry_times[p.ticket] = p.time # broker time fallback

            elapsed_sec = now - self.trade_entry_times.get(p.ticket, now)

            # ── Condition 1: Fast Profit Snatch (+2.0 pips hit anytime) ──
            if profit_pips >= PROFIT_SNATCH_PIPS:
                log.info(f"💰 PROFIT SNATCHED! #{p.ticket} {p.symbol} +{profit_pips:.1f} pips (+${p.profit:.2f}) banked in {elapsed_sec:.0f}s!")
                self.close_position(p, "Fast Profit Bank")
                continue

            # ── Condition 2: 1-Minute Hard Exit Rule ──
            if elapsed_sec >= MAX_HOLD_SECONDS:
                if p.profit > 0:
                    log.info(f"⏱️ 1-MIN PROFIT EXIT: #{p.ticket} {p.symbol} reached 60s with +${p.profit:.2f}. Banked and hunting next!")
                else:
                    log.info(f"⏱️ 1-MIN TIMEOUT EXIT: #{p.ticket} {p.symbol} stalled for 60s ({p.profit:+.2f}). Closed to free capital!")
                self.close_position(p, "1-Min Exit")
                continue

            # ── Condition 3: Quick Breakeven Lock at +1.5 pips ──
            if profit_pips >= 1.5:
                at_be = (p.sl >= p.price_open) if is_buy else (p.sl <= p.price_open and p.sl > 0)
                if not at_be:
                    digits = mt5.symbol_info(p.symbol).digits
                    be_price = round(p.price_open + (0.3 * pip_size if is_buy else -0.3 * pip_size), digits)
                    req = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": p.ticket,
                        "symbol": p.symbol,
                        "sl": be_price,
                        "tp": p.tp,
                    }
                    mt5.order_send(req)

        return len(positions)

    def close_position(self, p, reason):
        order_type = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(p.symbol)
        price = tick.bid if p.type == 0 else tick.ask
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": p.ticket,
            "symbol": p.symbol,
            "volume": p.volume,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": MAGIC_NUMBER,
            "comment": reason[:10],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(req)
        if res and (res.retcode != mt5.TRADE_RETCODE_DONE and res.retcode != 10009):
            req['type_filling'] = mt5.ORDER_FILLING_FOK
            mt5.order_send(req)

        if p.ticket in self.trade_entry_times:
            del self.trade_entry_times[p.ticket]

    def scan_and_strike_setup(self, symbol):
        """Scans M1 micro-momentum bursts for instant entries."""
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 30)
        if rates is None or len(rates) < 15:
            return

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df.set_index('time')

        pip_size = get_pip(symbol)
        digits = mt5.symbol_info(symbol).digits
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return

        df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()
        df['ema13'] = df['close'].ewm(span=13, adjust=False).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3]

        lot = LOT_GOLD if symbol == 'XAUUSD' else LOT_FOREX

        # ── Setup A: Fast M1 Momentum Burst (EMA 5/13 Velocity) ──
        # Bullish Burst: Price breaks above EMA5 + EMA5 crosses above EMA13
        if last['close'] > last['ema5'] and last['ema5'] > last['ema13'] and last['close'] > last['open']:
            entry = tick.ask
            sl_pips = HARD_SL_PIPS if symbol != 'XAUUSD' else 15.0
            tp_pips = PROFIT_SNATCH_PIPS if symbol != 'XAUUSD' else 5.0
            sl = round(entry - (sl_pips * pip_size), digits)
            tp = round(entry + (tp_pips * pip_size), digits)
            log.info(f"⚡ FLASH STRIKE: BUY {symbol} {lot} lot! (M1 Velocity Burst)")
            self.execute_order(symbol, "BUY", lot, entry, sl, tp)

        # Bearish Burst: Price drops below EMA5 + EMA5 crosses below EMA13
        elif last['close'] < last['ema5'] and last['ema5'] < last['ema13'] and last['close'] < last['open']:
            entry = tick.bid
            sl_pips = HARD_SL_PIPS if symbol != 'XAUUSD' else 15.0
            tp_pips = PROFIT_SNATCH_PIPS if symbol != 'XAUUSD' else 5.0
            sl = round(entry + (sl_pips * pip_size), digits)
            tp = round(entry - (tp_pips * pip_size), digits)
            log.info(f"⚡ FLASH STRIKE: SELL {symbol} {lot} lot! (M1 Velocity Burst)")
            self.execute_order(symbol, "SELL", lot, entry, sl, tp)

    def execute_order(self, symbol, direction, lot, price, sl, tp):
        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 15,
            "magic": MAGIC_NUMBER,
            "comment": "FlashScalp",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(req)
        if res and (res.retcode == mt5.TRADE_RETCODE_DONE or res.retcode == 10009):
            log.info(f"🎯 EXECUTED: {direction} {symbol} {lot} lot @ {price} | TP Target: +${PROFIT_SNATCH_PIPS * 10 * lot:.1f}")
            self.trade_entry_times[res.order] = time.time()
        else:
            req['type_filling'] = mt5.ORDER_FILLING_FOK
            res2 = mt5.order_send(req)
            if res2 and (res2.retcode == mt5.TRADE_RETCODE_DONE or res2.retcode == 10009):
                log.info(f"🎯 EXECUTED (FOK): {direction} {symbol} {lot} lot @ {price}")
                self.trade_entry_times[res2.order] = time.time()

    def run(self):
        if not self.connect():
            return

        try:
            while self.running:
                # 1. Manage 1-minute exits & profit snatch
                open_count = self.manage_flash_exits()

                # 2. Continuous hunting: immediately strike next setup
                if open_count < MAX_OPEN_POSITIONS:
                    open_syms = [p.symbol for p in (mt5.positions_get() or [])]
                    for s in SYMBOLS:
                        if s in open_syms:
                            continue
                        self.scan_and_strike_setup(s)

                time.sleep(1.5) # 1.5-second ultra-fast cycle

        except KeyboardInterrupt:
            log.info("Flash Scalper stopped.")
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    scalper = FlashScalper()
    scalper.run()
