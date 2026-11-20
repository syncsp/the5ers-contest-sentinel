"""
Real-Time Cross-Asset SMT, DXY Impact, and Institutional Setup Generator
Analyzes live GBPUSD trade impact and crafts 1:2 - 1:3 RR setups on secondary pairs.
"""

import sys
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone
import MetaTrader5 as mt5

mt5.initialize()

def get_pip(symbol):
    if "XAU" in symbol.upper():
        return 0.1
    return 0.01 if "JPY" in symbol.upper() else 0.0001

def fetch_data(symbol, timeframe, n_bars=100):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n_bars)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    return df

# 1. Live GBPUSD trade inspection
pos = mt5.positions_get(symbol="GBPUSD")
gbpusd_trade = pos[0]._asdict() if pos and len(pos) > 0 else None

# Check ticks
symbols = ['GBPUSD', 'EURUSD', 'USDCAD', 'USDJPY', 'GBPJPY', 'NZDUSD', 'AUDUSD']
ticks = {}
for s in symbols:
    t = mt5.symbol_info_tick(s)
    if t:
        pip = get_pip(s)
        ticks[s] = {
            'bid': t.bid,
            'ask': t.ask,
            'spread': round((t.ask - t.bid) / pip, 1),
            'pip': pip
        }

# Detailed analysis on live trade:
# GBPUSD sell from 1.30990, SL: 1.31130, TP: 1.30860
df_gu_m5 = fetch_data('GBPUSD', mt5.TIMEFRAME_M5, 30)
df_eu_m5 = fetch_data('EURUSD', mt5.TIMEFRAME_M5, 30)
df_ucad_m5 = fetch_data('USDCAD', mt5.TIMEFRAME_M5, 30)
df_uj_m5 = fetch_data('USDJPY', mt5.TIMEFRAME_M5, 30)
df_gj_m5 = fetch_data('GBPJPY', mt5.TIMEFRAME_M5, 30)
df_nzd_m5 = fetch_data('NZDUSD', mt5.TIMEFRAME_M5, 30)

# Check last 6 candles M5 momentum
gu_m5_last = df_gu_m5.tail(6)
eu_m5_last = df_eu_m5.tail(6)
ucad_m5_last = df_ucad_m5.tail(6)

print("=== LIVE GBPUSD TRADE CONTEXT ===")
if gbpusd_trade:
    current_pips = (gbpusd_trade['price_open'] - ticks['GBPUSD']['bid']) / 0.0001
    dist_to_tp = (ticks['GBPUSD']['bid'] - gbpusd_trade['tp']) / 0.0001
    dist_to_sl = (gbpusd_trade['sl'] - ticks['GBPUSD']['ask']) / 0.0001
    print(f"Ticket: {gbpusd_trade['ticket']}, Vol: {gbpusd_trade['volume']}")
    print(f"Open: {gbpusd_trade['price_open']}, Current: {ticks['GBPUSD']['bid']}, PnL Pips: +{current_pips:.1f}p, Profit: ${gbpusd_trade['profit']}")
    print(f"Distance to TP (1.30860): {dist_to_tp:.1f} pips | Distance to SL (1.31130): {dist_to_sl:.1f} pips")

# Check SMT on M5 between EURUSD and GBPUSD
# Compare M5 swing lows
gu_lows = df_gu_m5['low'].iloc[-12:].tolist()
eu_lows = df_eu_m5['low'].iloc[-12:].tolist()
print(f"GBPUSD last 5 M5 lows: {gu_lows[-5:]}")
print(f"EURUSD last 5 M5 lows: {eu_lows[-5:]}")
print(f"USDCAD last 5 M5 highs: {df_ucad_m5['high'].iloc[-5:].tolist()}")

# Check liquidity targets for GBPUSD TP
# Where is the sell side liquidity (SSL) below 1.30900?
df_gu_m15 = fetch_data('GBPUSD', mt5.TIMEFRAME_M15, 60)
today_utc = datetime.now(timezone.utc).date()
today_bars_gu = df_gu_m15[df_gu_m15['time'].dt.date == today_utc]
asian_low_gu = today_bars_gu[(today_bars_gu['time'].dt.hour >= 0) & (today_bars_gu['time'].dt.hour < 6)]['low'].min()
print(f"GBPUSD Asian Low: {asian_low_gu}")
print(f"Today's Low so far: {today_bars_gu['low'].min()}")

