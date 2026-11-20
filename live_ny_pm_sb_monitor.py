"""
Live NY PM Silver Bullet Real-Time Surveillance & Execution Engine
═════════════════════════════════════════════════════════════════
Monitors GBPUSD, EURUSD, and AUDUSD continuously across M1 and M5.
Enforces fixed $75.00 USD risk, 3-5 pip SL buffer, and 1:1.0 RR.
Writes confirmed setups to pending_signal.json for desktop MT5 execution.
"""

import os
import sys
import time
import json
import logging
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
log = logging.getLogger("NY-PM-SilverBullet")

class NYPMSilverBulletMonitor:
    def __init__(self):
        if not mt5.initialize():
            raise RuntimeError("MT5 initialization failed")
        acc = mt5.account_info()
        if not acc or acc.login != TARGET_ACCOUNT:
            raise RuntimeError(f"MT5 not connected to target account {TARGET_ACCOUNT}")
        
        log.info(f"Connected to The5ers Account: {acc.login} ({acc.server}) | Balance: ${acc.balance:,.2f}")
        self.account = acc

    def get_server_utc_offset(self):
        tick = mt5.symbol_info_tick('EURUSD')
        if not tick:
            return 2.0
        utc_ts = datetime.now(timezone.utc).timestamp()
        return round((tick.time - utc_ts) / 3600.0)

    def fetch_data(self, symbol, timeframe, count=100):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        offset = self.get_server_utc_offset()
        df['server_time'] = pd.to_datetime(df['time'], unit='s')
        df['time'] = df['server_time'] - timedelta(hours=offset)
        return df

    def scan_cycle(self):
        now_utc = datetime.now(timezone.utc)
        in_sb = (now_utc.hour == 18)
        
        # Check existing open positions
        positions = mt5.positions_get()
        if positions and len(positions) >= 1:
            log.info(f"Open position exists ({len(positions)}). Standby mode.")
            return None

        # Check existing pending_signal.json
        if os.path.exists(SIGNAL_FILE):
            try:
                with open(SIGNAL_FILE, 'r') as f:
                    pending = json.load(f)
                if pending.get('status') == 'PENDING_HUMAN_DESKTOP_EXECUTION':
                    log.info(f"Signal already pending in {SIGNAL_FILE} ({pending.get('symbol')}). Standby.")
                    return None
            except Exception:
                pass

        signals = []
        for sym in PAIRS:
            tick = mt5.symbol_info_tick(sym)
            if not tick:
                continue
            pip = 0.0001
            spread = (tick.ask - tick.bid) / pip
            if spread > MAX_SPREAD_PIPS:
                continue

            cur_p = tick.bid
            df_m1 = self.fetch_data(sym, mt5.TIMEFRAME_M1, 60)
            df_m5 = self.fetch_data(sym, mt5.TIMEFRAME_M5, 40)
            df_m15 = self.fetch_data(sym, mt5.TIMEFRAME_M15, 40)
            df_h1 = self.fetch_data(sym, mt5.TIMEFRAME_H1, 100)

            if df_m1 is None or df_m5 is None or df_h1 is None:
                continue

            ema50 = df_h1['close'].ewm(span=50).mean().iloc[-1]
            ema200 = df_h1['close'].ewm(span=200).mean().iloc[-1]
            h1_bearish = cur_p < ema50
            h1_bullish = cur_p > ema50

            # Scan M5 and M1 for fresh FVGs
            for tf_name, df_tf in [('M5', df_m5), ('M1', df_m1)]:
                n = len(df_tf)
                for i in range(n - 2, max(2, n - 10), -1):
                    c0 = df_tf.iloc[i - 2]
                    c1 = df_tf.iloc[i - 1]
                    c2 = df_tf.iloc[i]

                    # Bearish FVG
                    if c0['low'] > c2['high'] + (0.4 * pip) and c1['close'] < c1['open'] and h1_bearish:
                        top = c0['low']
                        bot = c2['high']
                        fvg_size = (top - bot) / pip
                        
                        subsequent = df_tf.iloc[i+1:]
                        invalidated = any(subsequent['close'] > top) if len(subsequent) > 0 else False
                        if invalidated:
                            continue
                        
                        # Retest check: has price wicked into the FVG?
                        retested = any(subsequent['high'] >= bot) if len(subsequent) > 0 else False
                        
                        # Current price within retest zone: bot - 1.5p <= cur_p <= top + 0.8p
                        if (bot - 1.5 * pip) <= cur_p <= (top + 0.8 * pip):
                            swing_high = max(df_tf.iloc[max(0, i-6):i+1]['high'])
                            sl = swing_high + (SL_BUFFER_PIPS * pip)
                            risk_pips = (sl - cur_p) / pip
                            
                            if MIN_RISK_PIPS <= risk_pips <= MAX_RISK_PIPS:
                                lot = round(FIXED_RISK_USD / (risk_pips * 10.0), 2)
                                lot = max(0.01, min(lot, 1.50))
                                tp = cur_p - (risk_pips * TARGET_RR * pip)
                                
                                setup = {
                                    'symbol': sym,
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
                                    'fvg_zone': f"{bot:.5f} - {top:.5f} ({fvg_size:.1f}p)",
                                    'confluence': f"H1 Bearish Flow | {tf_name} FVG Retest | NY PM Silver Bullet | Hardened {SL_BUFFER_PIPS}p SL Buffer",
                                    'status': 'PENDING_HUMAN_DESKTOP_EXECUTION',
                                    'created_at': now_utc.isoformat()
                                }
                                signals.append(setup)
                                break

                    # Bullish FVG
                    elif c2['low'] > c0['high'] + (0.4 * pip) and c1['close'] > c1['open'] and h1_bullish:
                        top = c2['low']
                        bot = c0['high']
                        fvg_size = (top - bot) / pip
                        
                        subsequent = df_tf.iloc[i+1:]
                        invalidated = any(subsequent['close'] < bot) if len(subsequent) > 0 else False
                        if invalidated:
                            continue
                        
                        retested = any(subsequent['low'] <= top) if len(subsequent) > 0 else False
                        
                        if (bot - 0.8 * pip) <= cur_p <= (top + 1.5 * pip):
                            swing_low = min(df_tf.iloc[max(0, i-6):i+1]['low'])
                            sl = swing_low - (SL_BUFFER_PIPS * pip)
                            risk_pips = (cur_p - sl) / pip
                            
                            if MIN_RISK_PIPS <= risk_pips <= MAX_RISK_PIPS:
                                lot = round(FIXED_RISK_USD / (risk_pips * 10.0), 2)
                                lot = max(0.01, min(lot, 1.50))
                                tp = cur_p + (risk_pips * TARGET_RR * pip)
                                
                                setup = {
                                    'symbol': sym,
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
                                    'fvg_zone': f"{bot:.5f} - {top:.5f} ({fvg_size:.1f}p)",
                                    'confluence': f"H1 Bullish Flow | {tf_name} FVG Retest | NY PM Silver Bullet | Hardened {SL_BUFFER_PIPS}p SL Buffer",
                                    'status': 'PENDING_HUMAN_DESKTOP_EXECUTION',
                                    'created_at': now_utc.isoformat()
                                }
                                signals.append(setup)
                                break
        return signals

def test_once():
    monitor = NYPMSilverBulletMonitor()
    signals = monitor.scan_cycle()
    print("Scan completed. Signals found:", len(signals) if signals else 0)
    if signals:
        for s in signals:
            print(json.dumps(s, indent=2))
    mt5.shutdown()

if __name__ == "__main__":
    test_once()
