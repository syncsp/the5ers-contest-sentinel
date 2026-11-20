import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

if not mt5.initialize():
    print("MT5 initialization failed")
    exit(1)

pairs = ['GBPUSD', 'EURUSD', 'AUDUSD']

print("========================================================================")
print(f"   👑 NY PM SILVER BULLET PRE-MARKET RECONNAISSANCE")
print(f"   Current UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("========================================================================")

for sym in pairs:
    tick = mt5.symbol_info_tick(sym)
    if not tick:
        print(f"Could not get tick for {sym}")
        continue
    pip = 0.0001
    spread = (tick.ask - tick.bid) / pip
    print(f"\n================= {sym} (Bid: {tick.bid:.5f}, Ask: {tick.ask:.5f}, Spread: {spread:.1f}p) =================")

    # Fetch M15, M5, M1, H1
    rates_m15 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 100)
    df_m15 = pd.DataFrame(rates_m15)
    df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s', utc=True)

    rates_m5 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 100)
    df_m5 = pd.DataFrame(rates_m5)
    df_m5['time'] = pd.to_datetime(df_m5['time'], unit='s', utc=True)

    rates_m1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 100)
    df_m1 = pd.DataFrame(rates_m1)
    df_m1['time'] = pd.to_datetime(df_m1['time'], unit='s', utc=True)

    rates_h1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 200)
    df_h1 = pd.DataFrame(rates_h1)
    df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s', utc=True)

    today_utc = datetime.now(timezone.utc).date()
    df_today_m15 = df_m15[df_m15['time'].dt.date == today_utc]

    day_high = df_today_m15['high'].max()
    day_low = df_today_m15['low'].min()

    # Session liquidity pools
    asian_df = df_today_m15[(df_today_m15['time'].dt.hour >= 0) & (df_today_m15['time'].dt.hour < 6)]
    a_high = asian_df['high'].max() if len(asian_df) > 0 else 0
    a_low = asian_df['low'].min() if len(asian_df) > 0 else 0

    london_df = df_today_m15[(df_today_m15['time'].dt.hour >= 7) & (df_today_m15['time'].dt.hour < 11)]
    l_high = london_df['high'].max() if len(london_df) > 0 else 0
    l_low = london_df['low'].min() if len(london_df) > 0 else 0

    ny_am_df = df_today_m15[(df_today_m15['time'].dt.hour >= 12) & (df_today_m15['time'].dt.hour < 16)]
    ny_high = ny_am_df['high'].max() if len(ny_am_df) > 0 else 0
    ny_low = ny_am_df['low'].min() if len(ny_am_df) > 0 else 0

    cur_p = tick.bid
    print(f"Day Extrema: Low = {day_low:.5f} | High = {day_high:.5f} (Total Range: {(day_high - day_low)/pip:.1f} pips)")
    print(f"Asian Range (00-06 UTC):  Low = {a_low:.5f} | High = {a_high:.5f}")
    print(f"London Range (07-11 UTC): Low = {l_low:.5f} | High = {l_high:.5f}")
    print(f"NY AM Range (12-16 UTC):  Low = {ny_low:.5f} | High = {ny_high:.5f}")

    # Liquidity Sweeps
    print("Liquidity Pool Sweeps:")
    if a_high and day_high > a_high:
        print(f"  [SWEEP] Asian High ({a_high:.5f}) swept by {(day_high - a_high)/pip:.1f} pips")
    if a_low and day_low < a_low:
        print(f"  [SWEEP] Asian Low ({a_low:.5f}) swept by {(a_low - day_low)/pip:.1f} pips")
    if l_high and day_high > l_high:
        print(f"  [SWEEP] London High ({l_high:.5f}) swept by {(day_high - l_high)/pip:.1f} pips")
    if l_low and day_low < l_low:
        print(f"  [SWEEP] London Low ({l_low:.5f}) swept by {(l_low - day_low)/pip:.1f} pips")
    if ny_high and cur_p > ny_high:
        print(f"  [SWEEP] NY AM High ({ny_high:.5f}) swept by {(cur_p - ny_high)/pip:.1f} pips")
    if ny_low and cur_p < ny_low:
        print(f"  [SWEEP] NY AM Low ({ny_low:.5f}) swept by {(ny_low - cur_p)/pip:.1f} pips")

    # Trend / Higher Timeframe EMA
    ema50 = df_h1['close'].ewm(span=50).mean().iloc[-1]
    ema200 = df_h1['close'].ewm(span=200).mean().iloc[-1]
    bias = "BULLISH" if cur_p > ema50 and ema50 > ema200 else ("BEARISH" if cur_p < ema50 and ema50 < ema200 else "MIXED/NEUTRAL")
    print(f"H1 Trend: Price: {cur_p:.5f} | EMA50: {ema50:.5f} | EMA200: {ema200:.5f} | Flow Bias: {bias}")

    # Detect FVGs on M15, M5, M1
    def find_recent_fvgs(df, tf_name, count=5):
        fvgs = []
        n = len(df)
        for i in range(n - 2, max(2, n - 25), -1):
            c0 = df.iloc[i - 2]
            c1 = df.iloc[i - 1]
            c2 = df.iloc[i]
            # Bullish FVG
            if c2['low'] > c0['high'] + (0.3 * pip) and c1['close'] > c1['open']:
                top = c2['low']
                bot = c0['high']
                size = (top - bot) / pip
                # Check mitigation
                subsequent = df.iloc[i+1:]
                mitigated = any(subsequent['low'] <= bot) if len(subsequent) > 0 else False
                retested = any(subsequent['low'] <= top) if len(subsequent) > 0 else False
                fvgs.append({
                    'tf': tf_name, 'type': 'BULLISH', 'time': c1['time'],
                    'top': top, 'bottom': bot, 'size_pips': size,
                    'mitigated': mitigated, 'retested': retested,
                    'dist_to_top': (cur_p - top) / pip,
                    'dist_to_bot': (cur_p - bot) / pip
                })
            # Bearish FVG
            elif c0['low'] > c2['high'] + (0.3 * pip) and c1['close'] < c1['open']:
                top = c0['low']
                bot = c2['high']
                size = (top - bot) / pip
                subsequent = df.iloc[i+1:]
                mitigated = any(subsequent['high'] >= top) if len(subsequent) > 0 else False
                retested = any(subsequent['high'] >= bot) if len(subsequent) > 0 else False
                fvgs.append({
                    'tf': tf_name, 'type': 'BEARISH', 'time': c1['time'],
                    'top': top, 'bottom': bot, 'size_pips': size,
                    'mitigated': mitigated, 'retested': retested,
                    'dist_to_top': (top - cur_p) / pip,
                    'dist_to_bot': (bot - cur_p) / pip
                })
        return fvgs[:count]

    fvgs_m15 = find_recent_fvgs(df_m15, 'M15', 3)
    fvgs_m5 = find_recent_fvgs(df_m5, 'M5', 3)
    fvgs_m1 = find_recent_fvgs(df_m1, 'M1', 5)

    print(f"\nActive Unmitigated / Recent FVGs:")
    for f in fvgs_m15 + fvgs_m5 + fvgs_m1:
        if not f['mitigated']:
            print(f"  [{f['tf']}] {f['type']} FVG @ {f['bottom']:.5f} - {f['top']:.5f} ({f['size_pips']:.1f}p) formed at {f['time'].strftime('%H:%M')} UTC | Retested: {f['retested']} | Dist: {f['dist_to_bot']:.1f}p / {f['dist_to_top']:.1f}p")

mt5.shutdown()
