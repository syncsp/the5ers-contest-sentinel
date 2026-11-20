import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone, timedelta

mt5.initialize()
print(f"--- M1 TICK & BAR AUDIT AT {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')} ---")
for s in ['EURUSD', 'GBPUSD', 'AUDUSD']:
    rates = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_M1, 0, 4)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s') - timedelta(hours=2)
    t = mt5.symbol_info_tick(s)
    pip = 0.0001
    spread = (t.ask - t.bid) / pip
    print(f"\n{s} | Current Bid: {t.bid:.5f} | Ask: {t.ask:.5f} | Spread: {spread:.1f}p")
    for _, r in df.iterrows():
        b_type = 'BULL' if r['close'] >= r['open'] else 'BEAR'
        body = abs(r['close'] - r['open']) / pip
        print(f"  {r['time'].strftime('%H:%M')} UTC | O: {r['open']:.5f} | H: {r['high']:.5f} | L: {r['low']:.5f} | C: {r['close']:.5f} | {b_type} ({body:.1f}p)")
mt5.shutdown()
