import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone, timedelta

if not mt5.initialize():
    print("Failed to initialize MT5")
    exit(1)

positions = mt5.positions_get(ticket=17663870)
if not positions:
    positions = mt5.positions_get()

pip = 0.0001
if positions:
    for p in positions:
        d = p._asdict()
        is_sell = d['type'] == 1
        direction = "SELL" if is_sell else "BUY"
        pips_profit = (d['price_open'] - d['price_current']) / pip if is_sell else (d['price_current'] - d['price_open']) / pip
        dist_tp = (d['price_current'] - d['tp']) / pip if is_sell else (d['tp'] - d['price_current']) / pip
        dist_sl = (d['sl'] - d['price_current']) / pip if is_sell else (d['price_current'] - d['sl']) / pip
        print("=" * 65)
        print(f"POSITION AUDIT: Ticket #{d['ticket']} | {d['symbol']} {direction} {d['volume']} lot")
        print(f"Entry Price:     {d['price_open']:.5f}")
        print(f"Current Price:   {d['price_current']:.5f}")
        print(f"Profit / Loss:   ${d['profit']:+.2f} USD ({pips_profit:+.1f} pips)")
        print(f"Stop Loss:       {d['sl']:.5f} (Buffer: {dist_sl:.1f} pips)")
        print(f"Take Profit:     {d['tp']:.5f} (Distance to TP: {dist_tp:.1f} pips)")
        print("=" * 65)

# Recent M1 bars
rates = mt5.copy_rates_from_pos('GBPUSD', mt5.TIMEFRAME_M1, 0, 7)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s') - timedelta(hours=2)
print("Recent GBPUSD M1 Candles (UTC):")
for _, r in df.iterrows():
    b_type = "BULL" if r['close'] >= r['open'] else "BEAR"
    body = abs(r['close'] - r['open']) / pip
    t_str = r['time'].strftime('%H:%M')
    print(f"  {t_str} UTC │ O: {r['open']:.5f} │ H: {r['high']:.5f} │ L: {r['low']:.5f} │ C: {r['close']:.5f} │ {b_type} ({body:.1f}p)")

mt5.shutdown()
