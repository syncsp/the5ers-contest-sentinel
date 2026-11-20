"""
Asymmetric Setup & Order Flow Delivery Tracker
══════════════════════════════════════════════
Tracks GBPUSD Ticket #17663870 delivery toward 1:1.5, 1:2.0, and 1:3.0 RR.
Computes order flow delta, momentum, and volume metrics on M1 and M5.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

if not mt5.initialize():
    print("Failed to initialize MT5")
    exit(1)

pos = mt5.positions_get(ticket=17663870)
if not pos:
    pos = mt5.positions_get()

pip = 0.0001

if pos:
    p = pos[0]._asdict()
    cur_p = p['price_current']
    entry = p['price_open']
    sl = p['sl']
    tp = p['tp']
    vol = p['volume']
    pnl = p['profit']
    profit_pips = (entry - cur_p) / pip
    risk_pips = (sl - entry) / pip
    
    # Asymmetric targets
    t1_asian_low = 1.30782
    t1_dist = (cur_p - t1_asian_low) / pip
    t1_rr = (entry - t1_asian_low) / (sl - entry)
    t1_pnl = (entry - t1_asian_low) / pip * 10.0 * vol

    t2_2r = 1.30710
    t2_dist = (cur_p - t2_2r) / pip
    t2_rr = (entry - t2_2r) / (sl - entry)
    t2_pnl = (entry - t2_2r) / pip * 10.0 * vol

    t3_3r = entry - (3.0 * (sl - entry))
    t3_dist = (cur_p - t3_3r) / pip
    t3_pnl = (entry - t3_3r) / pip * 10.0 * vol

    print("=" * 70)
    print(f"👑 POSITION STATUS: Ticket #{p['ticket']} | {p['symbol']} SELL {vol} lot")
    print(f"Entry:          {entry:.5f}")
    print(f"Current Price:  {cur_p:.5f}")
    print(f"Unrealized PnL: ${pnl:+.2f} USD ({profit_pips:+.1f} pips)")
    print(f"Stop Loss:      {sl:.5f} (Buffer: {(sl - cur_p)/pip:.1f} pips)")
    print(f"Current TP:     {tp:.5f}")
    print("-" * 70)
    print("🎯 ASYMMETRIC DOWNSIDE TARGETS & REWARD METRICS:")
    print(f"  • Target 1 (Major Asian Low SSL @ 1.30782): {t1_dist:+.1f}p away | {t1_rr:.2f}R | +${t1_pnl:.2f} USD")
    print(f"  • Target 2 (1:2.0 RR Asymmetric @ 1.30710):  {t2_dist:+.1f}p away | {t2_rr:.2f}R | +${t2_pnl:.2f} USD")
    print(f"  • Target 3 (1:3.0 RR Full Extension @ {t3_3r:.5f}): {t3_dist:+.1f}p away | 3.00R | +${t3_pnl:.2f} USD")
    print("=" * 70)

# M1 Order Flow & Volume Delta
rates_m1 = mt5.copy_rates_from_pos('GBPUSD', mt5.TIMEFRAME_M1, 0, 15)
df_m1 = pd.DataFrame(rates_m1)
df_m1['time'] = pd.to_datetime(df_m1['time'], unit='s') - timedelta(hours=2)

print("\n📊 LIVE GBPUSD M1 ORDER FLOW & TICK VOLUME DELTA:")
cum_delta = 0
for _, r in df_m1.iloc[-10:].iterrows():
    b_type = "BULL" if r['close'] >= r['open'] else "BEAR"
    body = abs(r['close'] - r['open']) / pip
    v_delta = r['tick_volume'] if r['close'] >= r['open'] else -r['tick_volume']
    cum_delta += v_delta
    t_str = r['time'].strftime('%H:%M')
    print(f"  {t_str} UTC │ {r['open']:.5f} -> {r['close']:.5f} (H:{r['high']:.5f} L:{r['low']:.5f}) │ {b_type:<4} {body:4.1f}p │ Vol: {r['tick_volume']:4d} │ Delta: {v_delta:+5d} │ CumDelta: {cum_delta:+6d}")

# M5 Structure & Order Flow
rates_m5 = mt5.copy_rates_from_pos('GBPUSD', mt5.TIMEFRAME_M5, 0, 8)
df_m5 = pd.DataFrame(rates_m5)
df_m5['time'] = pd.to_datetime(df_m5['time'], unit='s') - timedelta(hours=2)

print("\n📊 LIVE GBPUSD M5 CANDLES & ORDER FLOW:")
for _, r in df_m5.iterrows():
    b_type = "BULL" if r['close'] >= r['open'] else "BEAR"
    body = abs(r['close'] - r['open']) / pip
    v_delta = r['tick_volume'] if r['close'] >= r['open'] else -r['tick_volume']
    t_str = r['time'].strftime('%H:%M')
    print(f"  {t_str} UTC │ O: {r['open']:.5f} H: {r['high']:.5f} L: {r['low']:.5f} C: {r['close']:.5f} │ {b_type:<4} {body:4.1f}p │ Vol: {r['tick_volume']:4d}")

# Momentum Indicator (RSI 14 on M1 & M5)
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

rsi_m1 = calc_rsi(df_m1['close'], 14).iloc[-1]
rates_m5_all = mt5.copy_rates_from_pos('GBPUSD', mt5.TIMEFRAME_M5, 0, 30)
df_m5_all = pd.DataFrame(rates_m5_all)
rsi_m5 = calc_rsi(df_m5_all['close'], 14).iloc[-1]

print("\n⚡ MOMENTUM & DELIVERY METRICS:")
print(f"  M1 RSI (14): {rsi_m1:.1f} ({'Oversold' if rsi_m1 < 30 else ('Overbought' if rsi_m1 > 70 else 'Neutral/Bearish Momentum')})")
print(f"  M5 RSI (14): {rsi_m5:.1f} ({'Oversold' if rsi_m5 < 30 else ('Overbought' if rsi_m5 > 70 else 'Bearish Trend Continuation')})")

mt5.shutdown()
