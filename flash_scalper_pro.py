"""
FTMO Professional Flash Scalper (Fine-Tuned M1/M3 High-Success Engine)
═══════════════════════════════════════════════════════════════════════
Fine-Tuning Upgrades based on Live Trade Results:
1. EXCLUDED GOLD: Focuses exclusively on low-spread Forex majors (EURUSD, GBPUSD, AUDUSD, USDJPY)
2. EXTENDED DURATION: 180s (3-min) breathing room instead of 60s premature timeout cuts
3. ULTRA-FAST PROFIT SNATCH: Banks cash immediately at +1.5 to +2.5 pips
4. QUICK BREAKEVEN: Pulls SL to entry at +1.2 pips profit (Zero-Loss Mode)
5. CONFLUENCE FILTER: Requires M1 momentum + M5 trend direction alignment
6. CALIBRATED LOT: 0.25 lots (Clean ~$6.25 to $12.50 profit per win, strict risk control)
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
FOREX_MAJORS = ['EURUSD', 'GBPUSD', 'AUDUSD', 'USDJPY']
LOT_SIZE = 0.25           # Calibrated high-success lot size
MAX_HOLD_SECONDS = 180    # 3-minute max hold (gives trades room to hit target)
PROFIT_SNATCH_PIPS = 2.0  # Immediate cash snatch
QUICK_BE_PIPS = 1.2       # Instant breakeven lock
HARD_SL_PIPS = 5.0        # Tight protective stop
MAX_POSITIONS = 2         # FTMO position limit
MAGIC_NUMBER = 888111
POLL_INTERVAL_SEC = 2.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("flash_pro.log", encoding="utf-8")
    ]
)
log = logging.getLogger("FlashPro")

def get_pip(symbol):
    return 0.01 if "JPY" in symbol.upper() else 0.0001

class FlashScalperPro:
    def __init__(self):
        self.running = True
        self.entry_times = {}

    def connect(self):
        if not mt5.initialize():
            log.error(f"MT5 Init Error: {mt5.last_error()}")
            return False
        # Always guarantee connection to FTMO-Demo account
        mt5.login(1515335705, server="FTMO-Demo")
        info = mt5.account_info()
        log.info("=" * 65)
        log.info("   ⚡ FTMO PRO FLASH SCALPER ACTIVATED (FINE-TUNED) ⚡")
        log.info(f"   Account:        {info.login} ({info.server})")
        log.info(f"   Balance:        ${info.balance:.2f} USD")
        log.info(f"   Pairs:          {', '.join(FOREX_MAJORS)} (Gold Excluded)")
        log.info(f"   Lot Size:       {LOT_SIZE} (~$12.50 target per win)")
        log.info(f"   Profit Snatch:  +{PROFIT_SNATCH_PIPS} pips (Instant bank)")
        log.info(f"   Auto-BE:        +{QUICK_BE_PIPS} pips (Risk-Free Lock)")
        log.info(f"   Max Hold:       {MAX_HOLD_SECONDS}s (3-Min Cycle)")
        log.info("=" * 65)
        return True

    def manage_active_scalps(self):
        positions = mt5.positions_get()
        if not positions:
            return 0

        now = time.time()

        for p in positions:
            pip_size = get_pip(p.symbol)
            is_buy = (p.type == 0)
            digits = mt5.symbol_info(p.symbol).digits
            profit_pips = ((p.price_current - p.price_open) if is_buy else (p.price_open - p.price_current)) / pip_size

            if p.ticket not in self.entry_times:
                self.entry_times[p.ticket] = p.time

            elapsed = now - self.entry_times.get(p.ticket, now)

            # 1. Instant Profit Snatch (+2.0 pips hit)
            if profit_pips >= PROFIT_SNATCH_PIPS:
                log.info(f"💰 PROFIT SNATCHED! #{p.ticket} {p.symbol} +{profit_pips:.1f} pips (+${p.profit:.2f}) banked in {elapsed:.0f}s!")
                self.close_position(p, "Fast Profit")
                continue

            # 2. Quick Breakeven Lock at +1.2 pips
            if profit_pips >= QUICK_BE_PIPS:
                at_be = (p.sl >= p.price_open) if is_buy else (p.sl <= p.price_open and p.sl > 0)
                if not at_be:
                    be_price = round(p.price_open + (0.3 * pip_size if is_buy else -0.3 * pip_size), digits)
                    req = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": p.ticket,
                        "symbol": p.symbol,
                        "sl": be_price,
                        "tp": p.tp,
                    }
                    res = mt5.order_send(req)
                    if res and (res.retcode == mt5.TRADE_RETCODE_DONE or res.retcode == 10009):
                        log.info(f"🔒 BREAKEVEN SECURED: #{p.ticket} {p.symbol} SL locked at {be_price} (Zero-Risk Active)")

            # 3. 3-Minute Hard Timeout Exit
            if elapsed >= MAX_HOLD_SECONDS:
                if p.profit > 0:
                    log.info(f"⏱️ 3-MIN PROFIT EXIT: #{p.ticket} {p.symbol} reached timeout with +${p.profit:.2f}. Banked!")
                else:
                    log.info(f"⏱️ 3-MIN CUT EXIT: #{p.ticket} {p.symbol} stalled ({p.profit:+.2f}). Closed to free slot.")
                self.close_position(p, "Timeout")
                continue

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

        if p.ticket in self.entry_times:
            del self.entry_times[p.ticket]

    def scan_confluence_entry(self, symbol):
        """M5 Trend Direction + M1 Momentum Trigger."""
        rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 25)
        rates_m1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 30)
        if rates_m5 is None or len(rates_m5) < 15 or rates_m1 is None or len(rates_m1) < 15:
            return

        df5 = pd.DataFrame(rates_m5)
        df1 = pd.DataFrame(rates_m1)

        # M5 Trend (EMA 20)
        df5['ema20'] = df5['close'].ewm(span=20, adjust=False).mean()
        m5_trend = "BULL" if df5['close'].iloc[-1] > df5['ema20'].iloc[-1] else "BEAR"

        pip_size = get_pip(symbol)
        digits = mt5.symbol_info(symbol).digits
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return

        # Spread Gate: Skip if spread > 1.2 pips
        spread_pips = (tick.ask - tick.bid) / pip_size
        if spread_pips > 1.2:
            return

        last1 = df1.iloc[-1]
        prev1 = df1.iloc[-2]
        prev2 = df1.iloc[-3]

        # ── BUY: M5 Bullish Trend + M1 Bullish Imbalance / Velocity ──
        if m5_trend == "BULL" and (last1['low'] > prev2['high'] or last1['close'] > prev1['high']) and (last1['close'] > last1['open']):
            entry = tick.ask
            sl = round(entry - (HARD_SL_PIPS * pip_size), digits)
            tp = round(entry + (PROFIT_SNATCH_PIPS * pip_size), digits)
            log.info(f"⚡ PRO TRIGGER: BUY {symbol} {LOT_SIZE} lot (M5 Bull + M1 Velocity)")
            self.execute_order(symbol, "BUY", entry, sl, tp)

        # ── SELL: M5 Bearish Trend + M1 Bearish Imbalance / Velocity ──
        elif m5_trend == "BEAR" and (last1['high'] < prev2['low'] or last1['close'] < prev1['low']) and (last1['close'] < last1['open']):
            entry = tick.bid
            sl = round(entry + (HARD_SL_PIPS * pip_size), digits)
            tp = round(entry - (PROFIT_SNATCH_PIPS * pip_size), digits)
            log.info(f"⚡ PRO TRIGGER: SELL {symbol} {LOT_SIZE} lot (M5 Bear + M1 Velocity)")
            self.execute_order(symbol, "SELL", entry, sl, tp)

    def execute_order(self, symbol, direction, price, sl, tp):
        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": LOT_SIZE,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 10,
            "magic": MAGIC_NUMBER,
            "comment": "FlashPro",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(req)
        if res and (res.retcode == mt5.TRADE_RETCODE_DONE or res.retcode == 10009):
            log.info(f"🎯 EXECUTED: {direction} {symbol} {LOT_SIZE} lot @ {price} | TP: {tp} (+${PROFIT_SNATCH_PIPS * 10 * LOT_SIZE:.2f})")
            self.entry_times[res.order] = time.time()
        else:
            req['type_filling'] = mt5.ORDER_FILLING_FOK
            res2 = mt5.order_send(req)
            if res2 and (res2.retcode == mt5.TRADE_RETCODE_DONE or res2.retcode == 10009):
                log.info(f"🎯 EXECUTED (FOK): {direction} {symbol} {LOT_SIZE} lot @ {price}")
                self.entry_times[res2.order] = time.time()

    def run(self):
        if not self.connect():
            return

        try:
            while self.running:
                active_count = self.manage_active_scalps()

                if active_count < MAX_POSITIONS:
                    open_syms = [p.symbol for p in (mt5.positions_get() or [])]
                    for s in FOREX_MAJORS:
                        if s in open_syms:
                            continue
                        self.scan_confluence_entry(s)

                time.sleep(POLL_INTERVAL_SEC)

        except KeyboardInterrupt:
            log.info("Flash Scalper Pro stopped.")
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    pro = FlashScalperPro()
    pro.run()
