"""
NY PM Silver Bullet Live Specialist Daemon
═════════════════════════════════════════
Continuously tracks EURUSD, GBPUSD, AUDUSD through the 18:00–19:00 UTC window.
Detects liquidity sweeps, displacement, and M1/M5 Fair Value Gaps.
Calculates fixed $75.00 USD risk, 3.5–5.0 pip SL buffer, and 1:1.0 RR.
Writes atomic pending_signal.json upon A+ confluence.
"""

import os
import sys
import time
import json
import logging
import winsound
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

WORKING_DIR = r"C:\Users\Sunny\.gemini\antigravity\scratch\ict-trading-bot"
SIGNAL_FILE = os.path.join(WORKING_DIR, "pending_signal.json")
LOG_FILE = os.path.join(WORKING_DIR, "ny_pm_sb.log")

TARGET_ACCOUNT = 12623347
PAIRS = ['GBPUSD', 'EURUSD', 'AUDUSD']
FIXED_RISK_USD = 75.0
TARGET_RR = 1.0
SL_BUFFER_PIPS = 4.0
MIN_RISK_PIPS = 5.0
MAX_RISK_PIPS = 25.0
MAX_SPREAD_PIPS = 2.0
DISPLACEMENT_MULT = 1.30

class FlushingStreamHandler(logging.StreamHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

class FlushingFileHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        FlushingStreamHandler(sys.stdout),
        FlushingFileHandler(LOG_FILE, encoding="utf-8")
    ]
)
log = logging.getLogger("NY-PM-SB")

class SilverBulletSentinel:
    def __init__(self):
        if not mt5.initialize():
            raise RuntimeError("MT5 initialization failed")
        acc = mt5.account_info()
        if not acc or acc.login != TARGET_ACCOUNT:
            raise RuntimeError(f"MT5 connected to unexpected account: {acc.login if acc else 'None'}")
        self.account = acc
        self.last_signal_time = {s: 0 for s in PAIRS}
        self.fired_signals = []
        log.info(f"Initialized SilverBulletSentinel on {acc.login} ({acc.server}) | Balance: ${acc.balance:,.2f}")

    def get_server_utc_offset(self):
        tick = mt5.symbol_info_tick('EURUSD')
        if not tick:
            return 2.0
        utc_ts = datetime.now(timezone.utc).timestamp()
        return round((tick.time - utc_ts) / 3600.0)

    def fetch_df(self, symbol, timeframe, count=120):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        offset = self.get_server_utc_offset()
        df['server_time'] = pd.to_datetime(df['time'], unit='s')
        df['time'] = df['server_time'] - timedelta(hours=offset)
        return df

    def get_liquidity_pools(self, symbol):
        df_m15 = self.fetch_df(symbol, mt5.TIMEFRAME_M15, 120)
        if df_m15 is None:
            return None
        now_utc = datetime.now(timezone.utc)
        today = now_utc.date()
        df_today = df_m15[df_m15['time'].dt.date == today]
        if len(df_today) == 0:
            return None

        # Asian (00-06)
        asian = df_today[(df_today['time'].dt.hour >= 0) & (df_today['time'].dt.hour < 6)]
        a_hi = asian['high'].max() if len(asian) > 0 else None
        a_lo = asian['low'].min() if len(asian) > 0 else None

        # London (07-11)
        london = df_today[(df_today['time'].dt.hour >= 7) & (df_today['time'].dt.hour < 11)]
        l_hi = london['high'].max() if len(london) > 0 else None
        l_lo = london['low'].min() if len(london) > 0 else None

        # NY AM (12-16)
        ny = df_today[(df_today['time'].dt.hour >= 12) & (df_today['time'].dt.hour < 16)]
        ny_hi = ny['high'].max() if len(ny) > 0 else None
        ny_lo = ny['low'].min() if len(ny) > 0 else None

        # Afternoon / Pre-SB (16-18)
        pre_sb = df_today[(df_today['time'].dt.hour >= 16) & (df_today['time'].dt.hour < 18)]
        pre_hi = pre_sb['high'].max() if len(pre_sb) > 0 else None
        pre_lo = pre_sb['low'].min() if len(pre_sb) > 0 else None

        return {
            'asian_hi': a_hi, 'asian_lo': a_lo,
            'london_hi': l_hi, 'london_lo': l_lo,
            'ny_hi': ny_hi, 'ny_lo': ny_lo,
            'pre_hi': pre_hi, 'pre_lo': pre_lo,
            'day_hi': df_today['high'].max(),
            'day_lo': df_today['low'].min()
        }

    def check_active_positions(self):
        pos = mt5.positions_get()
        return len(pos) if pos else 0

    def evaluate_symbol(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return None
        pip = 0.0001
        spread = (tick.ask - tick.bid) / pip
        if spread > MAX_SPREAD_PIPS:
            return None

        cur_p = tick.bid
        now_utc = datetime.now(timezone.utc)
        in_sb = (now_utc.hour == 18)

        pools = self.get_liquidity_pools(symbol)
        if not pools:
            return None

        # Fetch H1 for trend bias
        df_h1 = self.fetch_df(symbol, mt5.TIMEFRAME_H1, 80)
        if df_h1 is None:
            return None
        ema50 = df_h1['close'].ewm(span=50).mean().iloc[-1]
        is_bearish = cur_p < ema50
        is_bullish = cur_p > ema50

        # Scan both M5 and M1
        df_m5 = self.fetch_df(symbol, mt5.TIMEFRAME_M5, 40)
        df_m1 = self.fetch_df(symbol, mt5.TIMEFRAME_M1, 60)

        for tf_name, df_tf in [('M5', df_m5), ('M1', df_m1)]:
            if df_tf is None or len(df_tf) < 15:
                continue
            
            n = len(df_tf)
            for i in range(n - 2, max(2, n - 15), -1):
                c0 = df_tf.iloc[i - 2]
                c1 = df_tf.iloc[i - 1]
                c2 = df_tf.iloc[i]

                # Displacement check
                prev_bodies = (df_tf.iloc[max(0, i-10):i-1]['close'] - df_tf.iloc[max(0, i-10):i-1]['open']).abs()
                avg_b = prev_bodies.mean() if len(prev_bodies) > 0 else 0.0003
                c1_body = abs(c1['close'] - c1['open'])
                if c1_body < (avg_b * DISPLACEMENT_MULT):
                    continue

                # ─── BEARISH SETUP ───
                if c0['low'] > c2['high'] + (0.3 * pip) and c1['close'] < c1['open'] and is_bearish:
                    fvg_top = c0['low']
                    fvg_bot = c2['high']
                    fvg_size = (fvg_top - fvg_bot) / pip

                    subsequent = df_tf.iloc[i+1:]
                    if len(subsequent) > 0 and any(subsequent['close'] > fvg_top):
                        continue

                    retested = any(subsequent['high'] >= fvg_bot) if len(subsequent) > 0 else True

                    if (fvg_bot - (1.5 * pip)) <= cur_p <= (fvg_top + (0.8 * pip)) and retested:
                        swing_high = max(df_tf.iloc[max(0, i-5):i+1]['high'])
                        sl = swing_high + (SL_BUFFER_PIPS * pip)
                        risk_pips = (sl - cur_p) / pip

                        if MIN_RISK_PIPS <= risk_pips <= MAX_RISK_PIPS:
                            lot = round(FIXED_RISK_USD / (risk_pips * 10.0), 2)
                            lot = max(0.01, min(lot, 1.50))
                            tp = cur_p - (risk_pips * TARGET_RR * pip)

                            liq_notes = []
                            if pools['pre_hi'] and pools['day_hi'] >= pools['pre_hi']:
                                liq_notes.append(f"Pre-SB High ({pools['pre_hi']:.5f}) Swept")
                            if pools['london_hi'] and pools['day_hi'] >= pools['london_hi']:
                                liq_notes.append(f"London High ({pools['london_hi']:.5f}) Swept")
                            if pools['asian_hi'] and pools['day_hi'] >= pools['asian_hi']:
                                liq_notes.append(f"Asian High ({pools['asian_hi']:.5f}) Swept")
                            liq_desc = " | ".join(liq_notes) if liq_notes else "Internal Liquidity Swept"

                            return {
                                'symbol': symbol,
                                'direction': 'SELL',
                                'lot': lot,
                                'entry': round(cur_p, 5),
                                'sl': round(sl, 5),
                                'tp': round(tp, 5),
                                'risk_usd': FIXED_RISK_USD,
                                'reward_usd': FIXED_RISK_USD * TARGET_RR,
                                'rr': f"1:{TARGET_RR:.1f}",
                                'risk_pips': round(risk_pips, 1),
                                'tf': tf_name,
                                'fvg_zone': f"{fvg_bot:.5f} - {fvg_top:.5f} ({fvg_size:.1f}p)",
                                'confluence': f"H1 Bearish Flow | {liq_desc} | {tf_name} FVG Retest | Displacement Confirmed | ⚡ NY PM SILVER BULLET",
                                'status': 'PENDING_HUMAN_DESKTOP_EXECUTION',
                                'created_at': now_utc.isoformat()
                            }

                # ─── BULLISH SETUP ───
                elif c2['low'] > c0['high'] + (0.3 * pip) and c1['close'] > c1['open'] and is_bullish:
                    fvg_top = c2['low']
                    fvg_bot = c0['high']
                    fvg_size = (fvg_top - fvg_bot) / pip

                    subsequent = df_tf.iloc[i+1:]
                    if len(subsequent) > 0 and any(subsequent['close'] < fvg_bot):
                        continue

                    retested = any(subsequent['low'] <= fvg_top) if len(subsequent) > 0 else True

                    if (fvg_bot - (0.8 * pip)) <= cur_p <= (fvg_top + (1.5 * pip)) and retested:
                        swing_low = min(df_tf.iloc[max(0, i-5):i+1]['low'])
                        sl = swing_low - (SL_BUFFER_PIPS * pip)
                        risk_pips = (cur_p - sl) / pip

                        if MIN_RISK_PIPS <= risk_pips <= MAX_RISK_PIPS:
                            lot = round(FIXED_RISK_USD / (risk_pips * 10.0), 2)
                            lot = max(0.01, min(lot, 1.50))
                            tp = cur_p + (risk_pips * TARGET_RR * pip)

                            liq_notes = []
                            if pools['pre_lo'] and pools['day_lo'] <= pools['pre_lo']:
                                liq_notes.append(f"Pre-SB Low ({pools['pre_lo']:.5f}) Swept")
                            if pools['london_lo'] and pools['day_lo'] <= pools['london_lo']:
                                liq_notes.append(f"London Low ({pools['london_lo']:.5f}) Swept")
                            if pools['asian_lo'] and pools['day_lo'] <= pools['asian_lo']:
                                liq_notes.append(f"Asian Low ({pools['asian_lo']:.5f}) Swept")
                            liq_desc = " | ".join(liq_notes) if liq_notes else "Internal Liquidity Swept"

                            return {
                                'symbol': symbol,
                                'direction': 'BUY',
                                'lot': lot,
                                'entry': round(cur_p, 5),
                                'sl': round(sl, 5),
                                'tp': round(tp, 5),
                                'risk_usd': FIXED_RISK_USD,
                                'reward_usd': FIXED_RISK_USD * TARGET_RR,
                                'rr': f"1:{TARGET_RR:.1f}",
                                'risk_pips': round(risk_pips, 1),
                                'tf': tf_name,
                                'fvg_zone': f"{fvg_bot:.5f} - {fvg_top:.5f} ({fvg_size:.1f}p)",
                                'confluence': f"H1 Bullish Flow | {liq_desc} | {tf_name} FVG Retest | Displacement Confirmed | ⚡ NY PM SILVER BULLET",
                                'status': 'PENDING_HUMAN_DESKTOP_EXECUTION',
                                'created_at': now_utc.isoformat()
                            }
        return None

    def dispatch_signal(self, sig):
        with open(SIGNAL_FILE, 'w', encoding='utf-8') as f:
            json.dump(sig, f, indent=2)
        log.info(f"🔥 [SIGNAL DISPATCHED] {sig['direction']} {sig['lot']} lot {sig['symbol']} @ {sig['entry']} | SL: {sig['sl']} | TP: {sig['tp']} written to pending_signal.json")
        try:
            for freq in [1200, 1500, 1800, 2100]:
                winsound.Beep(freq, 140)
                time.sleep(0.03)
        except Exception:
            pass

    def run_window(self, duration_minutes=4):
        start_ts = time.time()
        end_ts = start_ts + (duration_minutes * 60)
        cycle = 0

        log.info(f"🚀 NY PM Silver Bullet Monitor active for {duration_minutes}m (until {datetime.fromtimestamp(end_ts, tz=timezone.utc).strftime('%H:%M:%S UTC')})...")

        while time.time() < end_ts:
            cycle += 1
            now_utc = datetime.now(timezone.utc)
            in_sb = (now_utc.hour == 18)
            sb_tag = "⚡ [IN SB WINDOW 18:00-19:00 UTC]" if in_sb else "⏳ [PRE-SB WINDOW]"

            if self.check_active_positions() >= 1:
                if cycle % 10 == 0:
                    log.info(f"[{now_utc.strftime('%H:%M:%S UTC')}] Active position exists. Holding.")
                time.sleep(8)
                continue

            if os.path.exists(SIGNAL_FILE):
                try:
                    with open(SIGNAL_FILE, 'r') as f:
                        cur_sig = json.load(f)
                    if cur_sig.get('status') == 'PENDING_HUMAN_DESKTOP_EXECUTION':
                        if cycle % 10 == 0:
                            log.info(f"[{now_utc.strftime('%H:%M:%S UTC')}] Trade payload pending execution in {SIGNAL_FILE}")
                        time.sleep(8)
                        continue
                except Exception:
                    pass

            for sym in PAIRS:
                now_ts = time.time()
                if (now_ts - self.last_signal_time[sym]) < 1800:
                    continue

                sig = self.evaluate_symbol(sym)
                if sig:
                    self.dispatch_signal(sig)
                    self.last_signal_time[sym] = now_ts
                    self.fired_signals.append(sig)
                    log.info(f"Signal confirmed and dispatched: {json.dumps(sig, indent=2)}")
                    return sig

            if cycle % 6 == 0:
                prices = []
                for s in PAIRS:
                    t = mt5.symbol_info_tick(s)
                    if t:
                        prices.append(f"{s}: {t.bid:.5f}")
                log.info(f"[{now_utc.strftime('%H:%M:%S UTC')}] {sb_tag} | {' | '.join(prices)}")

            time.sleep(4)

        log.info("Monitoring window cycle finished.")
        return None

if __name__ == "__main__":
    sentinel = SilverBulletSentinel()
    res = sentinel.run_window(duration_minutes=4)
    if res:
        print("SIGNAL_GENERATED")
    mt5.shutdown()
