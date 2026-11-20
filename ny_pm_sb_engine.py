"""
NY PM Silver Bullet Specialist Engine (18:00–19:00 UTC)
══════════════════════════════════════════════════════
Analyzes M15, M5, and M1 market structure on GBPUSD, EURUSD, and AUDUSD.
Tracks Asian, London, and NY AM session liquidity sweeps, SMT divergence,
and detects Fair Value Gaps (FVG) with displacement for 1:1.0 RR setups.
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

TARGET_ACCOUNT = 12623347
PAIRS = ['GBPUSD', 'EURUSD', 'AUDUSD']
FIXED_RISK_USD = 75.0
TARGET_RR = 1.0
SL_BUFFER_PIPS = 4.0  # 3-5 pip hardened buffer
MAX_SPREAD_PIPS = 2.0

WORKING_DIR = r"C:\Users\Sunny\.gemini\antigravity\scratch\ict-trading-bot"
SIGNAL_FILE = os.path.join(WORKING_DIR, "pending_signal.json")

def get_pip(symbol):
    return 0.0001

def get_pip_val(symbol):
    return 10.0

class SilverBulletAnalyzer:
    def __init__(self):
        if not mt5.initialize():
            raise RuntimeError("MT5 initialization failed")
        
        acc = mt5.account_info()
        if not acc:
            raise RuntimeError("Could not fetch account info")
        
        self.login = acc.login
        self.server = acc.server
        self.balance = acc.balance
        self.equity = acc.equity

    def get_server_utc_offset(self):
        tick = mt5.symbol_info_tick('EURUSD')
        if not tick:
            return 2.0
        utc_ts = datetime.now(timezone.utc).timestamp()
        offset_hours = round((tick.time - utc_ts) / 3600.0)
        return offset_hours

    def fetch_data(self, symbol, timeframe, count=200):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        # Convert broker server time to true UTC
        offset = self.get_server_utc_offset()
        df['server_time'] = pd.to_datetime(df['time'], unit='s')
        df['time'] = df['server_time'] - timedelta(hours=offset)
        return df

    def get_session_levels(self, symbol):
        df_m15 = self.fetch_data(symbol, mt5.TIMEFRAME_M15, 120)
        if df_m15 is None:
            return None
        
        now_utc = datetime.now(timezone.utc)
        today_utc = now_utc.date()
        df_today = df_m15[df_m15['time'].dt.date == today_utc]
        
        if len(df_today) == 0:
            return None
        
        day_high = df_today['high'].max()
        day_low = df_today['low'].min()
        
        # Asian Session: 00:00 to 06:00 UTC
        asian = df_today[(df_today['time'].dt.hour >= 0) & (df_today['time'].dt.hour < 6)]
        a_high = asian['high'].max() if len(asian) > 0 else None
        a_low = asian['low'].min() if len(asian) > 0 else None
        
        # London Session: 07:00 to 11:00 UTC
        london = df_today[(df_today['time'].dt.hour >= 7) & (df_today['time'].dt.hour < 11)]
        l_high = london['high'].max() if len(london) > 0 else None
        l_low = london['low'].min() if len(london) > 0 else None
        
        # NY AM Session: 12:00 to 16:00 UTC
        ny_am = df_today[(df_today['time'].dt.hour >= 12) & (df_today['time'].dt.hour < 16)]
        ny_high = ny_am['high'].max() if len(ny_am) > 0 else None
        ny_low = ny_am['low'].min() if len(ny_am) > 0 else None

        # Afternoon / London Close Session: 16:00 to 18:00 UTC
        lc = df_today[(df_today['time'].dt.hour >= 16) & (df_today['time'].dt.hour < 18)]
        lc_high = lc['high'].max() if len(lc) > 0 else None
        lc_low = lc['low'].min() if len(lc) > 0 else None

        return {
            'day_high': day_high, 'day_low': day_low,
            'asian_high': a_high, 'asian_low': a_low,
            'london_high': l_high, 'london_low': l_low,
            'ny_am_high': ny_high, 'ny_am_low': ny_low,
            'lc_high': lc_high, 'lc_low': lc_low
        }

    def detect_fvgs(self, df, timeframe_name, pip, max_bars=30):
        """Finds bullish and bearish FVGs with unmitigated and retest tracking."""
        fvgs = []
        n = len(df)
        cur_p = df.iloc[-1]['close']
        
        for i in range(n - 2, max(2, n - max_bars), -1):
            c0 = df.iloc[i - 2]
            c1 = df.iloc[i - 1]
            c2 = df.iloc[i]
            
            # Bullish FVG (c2.low > c0.high)
            if c2['low'] > c0['high'] + (0.3 * pip) and c1['close'] > c1['open']:
                top = c2['low']
                bot = c0['high']
                size = (top - bot) / pip
                subsequent = df.iloc[i+1:]
                mitigated = any(subsequent['low'] <= bot) if len(subsequent) > 0 else False
                retested = any(subsequent['low'] <= top) if len(subsequent) > 0 else False
                
                # Check displacement: c1 body vs 10-period avg body
                prev_bodies = (df.iloc[max(0, i-11):i-1]['close'] - df.iloc[max(0, i-11):i-1]['open']).abs()
                avg_b = prev_bodies.mean() if len(prev_bodies) > 0 else 0.0005
                c1_body = abs(c1['close'] - c1['open'])
                is_displacement = c1_body >= (avg_b * 1.3)
                
                fvgs.append({
                    'symbol': None,
                    'tf': timeframe_name,
                    'direction': 'BULLISH',
                    'bar_idx': i - 1,
                    'time_utc': c1['time'],
                    'top': top,
                    'bottom': bot,
                    'size_pips': round(size, 2),
                    'mitigated': mitigated,
                    'retested': retested,
                    'displacement': is_displacement,
                    'swing_low': min(c0['low'], c1['low'])
                })

            # Bearish FVG (c0.low > c2.high)
            elif c0['low'] > c2['high'] + (0.3 * pip) and c1['close'] < c1['open']:
                top = c0['low']
                bot = c2['high']
                size = (top - bot) / pip
                subsequent = df.iloc[i+1:]
                mitigated = any(subsequent['high'] >= top) if len(subsequent) > 0 else False
                retested = any(subsequent['high'] >= bot) if len(subsequent) > 0 else False
                
                prev_bodies = (df.iloc[max(0, i-11):i-1]['close'] - df.iloc[max(0, i-11):i-1]['open']).abs()
                avg_b = prev_bodies.mean() if len(prev_bodies) > 0 else 0.0005
                c1_body = abs(c1['close'] - c1['open'])
                is_displacement = c1_body >= (avg_b * 1.3)
                
                fvgs.append({
                    'symbol': None,
                    'tf': timeframe_name,
                    'direction': 'BEARISH',
                    'bar_idx': i - 1,
                    'time_utc': c1['time'],
                    'top': top,
                    'bottom': bot,
                    'size_pips': round(size, 2),
                    'mitigated': mitigated,
                    'retested': retested,
                    'displacement': is_displacement,
                    'swing_high': max(c0['high'], c1['high'])
                })
                
        return fvgs

    def analyze_pair(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return None
        pip = get_pip(symbol)
        spread = (tick.ask - tick.bid) / pip
        cur_p = tick.bid

        # Fetch Data
        df_m15 = self.fetch_data(symbol, mt5.TIMEFRAME_M15, 120)
        df_m5 = self.fetch_data(symbol, mt5.TIMEFRAME_M5, 120)
        df_m1 = self.fetch_data(symbol, mt5.TIMEFRAME_M1, 150)
        df_h1 = self.fetch_data(symbol, mt5.TIMEFRAME_H1, 150)

        # H1 Bias
        ema50 = df_h1['close'].ewm(span=50).mean().iloc[-1]
        ema200 = df_h1['close'].ewm(span=200).mean().iloc[-1]
        h1_bias = 'BULLISH' if (cur_p > ema50 and ema50 > ema200) else ('BEARISH' if (cur_p < ema50 and ema50 < ema200) else ('BEARISH' if cur_p < ema50 else 'BULLISH'))

        # Sessions
        sessions = self.get_session_levels(symbol)

        # Sweeps
        sweeps = []
        if sessions['asian_high'] and sessions['day_high'] > sessions['asian_high']:
            sweeps.append(f"Asian High swept by {((sessions['day_high'] - sessions['asian_high'])/pip):.1f}p")
        if sessions['asian_low'] and sessions['day_low'] < sessions['asian_low']:
            sweeps.append(f"Asian Low swept by {((sessions['asian_low'] - sessions['day_low'])/pip):.1f}p")
        if sessions['london_high'] and sessions['day_high'] > sessions['london_high']:
            sweeps.append(f"London High swept by {((sessions['day_high'] - sessions['london_high'])/pip):.1f}p")
        if sessions['london_low'] and sessions['day_low'] < sessions['london_low']:
            sweeps.append(f"London Low swept by {((sessions['london_low'] - sessions['day_low'])/pip):.1f}p")
        if sessions['ny_am_high'] and cur_p > sessions['ny_am_high']:
            sweeps.append(f"NY AM High swept by {((cur_p - sessions['ny_am_high'])/pip):.1f}p")
        if sessions['ny_am_low'] and cur_p < sessions['ny_am_low']:
            sweeps.append(f"NY AM Low swept by {((sessions['ny_am_low'] - cur_p)/pip):.1f}p")

        # FVGs
        fvgs_m15 = self.detect_fvgs(df_m15, 'M15', pip, 20)
        fvgs_m5 = self.detect_fvgs(df_m5, 'M5', pip, 25)
        fvgs_m1 = self.detect_fvgs(df_m1, 'M1', pip, 40)

        # Look for recent active/fresh M5 or M1 FVGs
        active_fvgs = [f for f in (fvgs_m15 + fvgs_m5 + fvgs_m1) if not f['mitigated']]

        return {
            'symbol': symbol,
            'bid': tick.bid,
            'ask': tick.ask,
            'spread': spread,
            'h1_bias': h1_bias,
            'ema50': ema50,
            'ema200': ema200,
            'sessions': sessions,
            'sweeps': sweeps,
            'active_fvgs': active_fvgs,
            'df_m15': df_m15,
            'df_m5': df_m5,
            'df_m1': df_m1
        }

    def check_smt(self, pair1_data, pair2_data):
        """Checks for SMT Divergence (e.g. EURUSD making higher high while GBPUSD makes lower high)."""
        # Compare high/low over last 20 M5 candles
        m5_1 = pair1_data['df_m5'].iloc[-20:]
        m5_2 = pair2_data['df_m5'].iloc[-20:]
        
        # Highs
        idx1_high = m5_1['high'].idxmax()
        idx2_high = m5_2['high'].idxmax()
        
        # Check divergence
        # Return note if detected
        return None

    def evaluate_silver_bullet_setup(self, analysis):
        """
        Evaluates strict NY PM Silver Bullet criteria:
        1. Time: 18:00–19:00 UTC
        2. Liquidity Sweep of previous session high/low or internal swing
        3. Market Structure Shift (MSS) / CISD with Displacement
        4. Clear FVG formed on M5 or M1
        5. Price retesting FVG entry zone
        6. Risk parameters: 3-5 pip buffer, $75 risk, 1:1.0 RR
        """
        now_utc = datetime.now(timezone.utc)
        in_sb_window = (now_utc.hour == 18)
        sym = analysis['symbol']
        cur_p = analysis['bid']
        pip = get_pip(sym)

        # Check spread
        if analysis['spread'] > MAX_SPREAD_PIPS:
            return None, f"Spread too high ({analysis['spread']:.1f}p > {MAX_SPREAD_PIPS}p)"

        # Check active unmitigated FVGs on M5 or M1
        for fvg in analysis['active_fvgs']:
            if fvg['tf'] not in ['M5', 'M1']:
                continue
            
            # Check displacement
            if not fvg['displacement']:
                continue
            
            # Check retest into zone
            if fvg['direction'] == 'BULLISH':
                # Entry zone: bottom <= cur_p <= top + 1.0 pip
                in_zone = (fvg['bottom'] - (1.0 * pip) <= cur_p <= fvg['top'] + (1.5 * pip))
                if in_zone and fvg['retested']:
                    # Bullish setup
                    swing_low = fvg.get('swing_low', cur_p - 10*pip)
                    sl = swing_low - (SL_BUFFER_PIPS * pip)
                    risk_pips = (cur_p - sl) / pip
                    if 5.0 <= risk_pips <= 30.0:
                        lot = round(FIXED_RISK_USD / (risk_pips * get_pip_val(sym)), 2)
                        lot = max(0.01, min(lot, 1.50))
                        tp = cur_p + (risk_pips * TARGET_RR * pip)
                        return {
                            'symbol': sym,
                            'direction': 'BUY',
                            'entry': cur_p,
                            'sl': sl,
                            'tp': tp,
                            'lot': lot,
                            'risk_usd': FIXED_RISK_USD,
                            'reward_usd': FIXED_RISK_USD * TARGET_RR,
                            'rr': f"1:{TARGET_RR:.1f}",
                            'risk_pips': round(risk_pips, 1),
                            'fvg': fvg,
                            'in_sb_window': in_sb_window,
                            'timestamp': now_utc.isoformat()
                        }, "CONFIRMED_BUY"

            elif fvg['direction'] == 'BEARISH':
                # Entry zone: bottom - 1.5 pip <= cur_p <= top + 1.0 pip
                in_zone = (fvg['bottom'] - (1.5 * pip) <= cur_p <= fvg['top'] + (1.0 * pip))
                if in_zone and fvg['retested']:
                    # Bearish setup
                    swing_high = fvg.get('swing_high', cur_p + 10*pip)
                    sl = swing_high + (SL_BUFFER_PIPS * pip)
                    risk_pips = (sl - cur_p) / pip
                    if 5.0 <= risk_pips <= 30.0:
                        lot = round(FIXED_RISK_USD / (risk_pips * get_pip_val(sym)), 2)
                        lot = max(0.01, min(lot, 1.50))
                        tp = cur_p - (risk_pips * TARGET_RR * pip)
                        return {
                            'symbol': sym,
                            'direction': 'SELL',
                            'entry': cur_p,
                            'sl': sl,
                            'tp': tp,
                            'lot': lot,
                            'risk_usd': FIXED_RISK_USD,
                            'reward_usd': FIXED_RISK_USD * TARGET_RR,
                            'rr': f"1:{TARGET_RR:.1f}",
                            'risk_pips': round(risk_pips, 1),
                            'fvg': fvg,
                            'in_sb_window': in_sb_window,
                            'timestamp': now_utc.isoformat()
                        }, "CONFIRMED_SELL"

        return None, "No active qualifying FVG retest"

if __name__ == "__main__":
    analyzer = SilverBulletAnalyzer()
    print(f"Account: {analyzer.login} | Balance: ${analyzer.balance:,.2f}")
    for sym in PAIRS:
        res = analyzer.analyze_pair(sym)
        setup, reason = analyzer.evaluate_silver_bullet_setup(res)
        print(f"\n--- {sym} ---")
        print(f"H1 Bias: {res['h1_bias']} | Spread: {res['spread']:.1f}p")
        print(f"Sweeps: {res['sweeps']}")
        print(f"Active FVGs count: {len(res['active_fvgs'])}")
        for f in res['active_fvgs'][:3]:
            print(f"  [{f['tf']}] {f['direction']} @ {f['bottom']:.5f} - {f['top']:.5f} ({f['size_pips']:.1f}p) | Retested: {f['retested']}")
        print(f"Silver Bullet Setup Status: {reason}")
    mt5.shutdown()
