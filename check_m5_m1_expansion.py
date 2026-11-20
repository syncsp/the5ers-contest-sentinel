"""
Check M5 / M1 Market Structure & Expansion Readiness
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone, timedelta

if not mt5.initialize():
    print("MT5 initialization failed")
    exit(1)

pip = 0.0001
pos = mt5.positions_get(ticket=17663870)
if pos:
    p = pos[0]._asdict()
    cur_p = p['price_current']
    entry = p['price_open']
    sl = p['sl']
    tp = p['tp']
    vol = p['volume']
    pnl = p['profit']
    profit_pips = (entry - cur_p) / pip
    print("=" * 65)
    print(f"POSITION: Ticket #{p['ticket']} | {p['symbol']} SELL {vol} lot")
    print(f"Entry:          {entry:.5f}")
    print(f"Current Price:  {cur_p:.5f}")
    print(f"Unrealized PnL: ${pnl:+.2f} USD ({profit_pips:+.1f} pips)")
    print(f"Stop Loss:      {sl:.5f} (Buffer: {(sl - cur_p)/pip:.1f} pips)")
    print(f"Current TP:     {tp:.5f} (Distance to TP: {(cur_p - tp)/pip:.1f} pips)")
    print(f"Distance to Asian Low (1.30782): {(cur_p - 1.30782)/pip:.1f} pips")
    print("=" * 65)
else:
    print("No open positions found.")

# M5 delivery from 18:00 UTC
rates_m5 = mt5.copy_rates_from_pos('GBPUSD', mt5.TIMEFRAME_M5, 0, 14)
df_m5 = pd.DataFrame(rates_m5)
df_m5['time'] = pd.to_datetime(df_m5['time'], unit='s') - timedelta(hours=2)

print("\n--- M5 ORDER FLOW (18:00 UTC - Present) ---")
for _, r in df_m5.iterrows():
    b_type = "BULL" if r['close'] >= r['open'] else "BEAR"
    body = abs(r['close'] - r['open']) / pip
    t_str = r['time'].strftime('%H:%M')
    print(f"  {t_str} UTC │ O: {r['open']:.5f} H: {r['high']:.5f} L: {r['low']:.5f} C: {r['close']:.5f} │ {b_type:<4} ({body:4.1f}p) │ Vol: {r['tick_volume']}")

# M1 delivery
rates_m1 = mt5.copy_rates_from_pos('GBPUSD', mt5.TIMEFRAME_M1, 0, 16)
df_m1 = pd.DataFrame(rates_m1)
df_m1['time'] = pd.to_datetime(df_m1['time'], unit='s') - timedelta(hours=2)

print("\n--- M1 RECENT ORDER FLOW & VOLUME DELTA ---")
cum_delta = 0
for _, r in df_m1.iloc[-12:].iterrows():
    b_type = "BULL" if r['close'] >= r['open'] else "BEAR"
    body = abs(r['close'] - r['open']) / pip
    v_delta = r['tick_volume'] if r['close'] >= r['open'] else -r['tick_volume']
    cum_delta += v_delta
    t_str = r['time'].strftime('%H:%M')
    print(f"  {t_str} UTC │ {r['open']:.5f} -> {r['close']:.5f} (H:{r['high']:.5f} L:{r['low']:.5f}) │ {b_type:<4} {body:4.1f}p │ Vol: {r['tick_volume']:4d} │ Delta: {v_delta:+5d} │ Cum: {cum_delta:+6d}")

# Check FVGs and Key Resistance
print("\n--- KEY M5 / M1 LEVELS & FVGS ---")
for i in range(len(df_m5)-2, max(0, len(df_m5)-8), -1):
    c0 = df_m5.iloc[i-2]
    c1 = df_m5.iloc[i-1]
    c2 = df_m5.iloc[i]
    if c0['low'] > c2['high'] + (0.3*pip) and c1['close'] < c1['open']:
        print(f"  M5 Bearish FVG: {c2['high']:.5f} - {c0['low']:.5f} ({(c0['low'] - c2['high'])/pip:.1f}p) formed at {c1['time'].strftime('%H:%M')} UTC")

# Check RSI
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

rsi_m5 = calc_rsi(df_m5['close'], 14).iloc[-1]
rsi_m1 = calc_rsi(df_m1['close'], 14).iloc[-1]
print(f"\nIndicators: M5 RSI = {rsi_m5:.1f} | M1 RSI = {rsi_m1:.1f}")

mt5.shutdown()
