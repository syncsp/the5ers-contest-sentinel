import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

def check_gold_target():
    if not mt5.initialize():
        print("Failed to initialize MT5")
        return

    symbol = "XAUUSD"
    tick = mt5.symbol_info_tick(symbol)
    server_time = datetime.fromtimestamp(tick.time)
    print("=" * 60)
    print(f"XAUUSD LIVE AUDIT AT {server_time}")
    print(f"Bid: {tick.bid:.2f} | Ask: {tick.ask:.2f} | Spread: ${(tick.ask - tick.bid):.2f}")
    print("=" * 60)

    # Daily Bar
    d1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 2)[-1]
    print(f"\n[DAILY STATUS]")
    print(f"Day High: ${d1['high']:.2f} | Day Low: ${d1['low']:.2f}")

    # Check M5 bars from the last 2 hours (24 bars)
    r_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 24)
    df_m5 = pd.DataFrame(r_m5)
    df_m5['datetime'] = pd.to_datetime(df_m5['time'], unit='s')
    
    print("\n[RECENT M5 BARS]")
    for _, r in df_m5.tail(12).iterrows():
        delta = r['close'] - r['open']
        bias = "BEARISH ▼" if delta < 0 else "BULLISH ▲"
        print(f"M5 {r['datetime']} | O:{r['open']:.2f} H:{r['high']:.2f} L:{r['low']:.2f} C:{r['close']:.2f} | {bias} (${delta:+.2f}) | Vol: {r['tick_volume']}")

    lowest_m5 = df_m5['low'].min()
    print(f"\nLowest price in recent M5 bars: ${lowest_m5:.2f}")

    asian_low = 3514.51
    print(f"\n[ASIAN LOW AUDIT ($3514.51)]")
    if d1['low'] <= asian_low:
        print(f"✓ YES! Gold has SWEPT/REACHED the Asian low target! Extreme Low = ${d1['low']:.2f} (Swept by ${asian_low - d1['low']:.2f})")
    else:
        dist_to_asian_low = tick.bid - asian_low
        print(f"✗ NOT YET REACHED. Current Day Low is ${d1['low']:.2f}. Distance to Asian Low: ${dist_to_asian_low:.2f}")

    # Recent M1 bars
    r_m1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 10)
    df_m1 = pd.DataFrame(r_m1)
    df_m1['datetime'] = pd.to_datetime(df_m1['time'], unit='s')
    print("\n[LAST 5 M1 BARS]")
    for _, r in df_m1.tail(5).iterrows():
        print(f"M1 {r['datetime']} | O:{r['open']:.2f} H:{r['high']:.2f} L:{r['low']:.2f} C:{r['close']:.2f} | Vol: {r['tick_volume']}")

    # Check open positions
    pos = mt5.positions_get()
    print(f"\n[ACCOUNT POSITIONS: {len(pos) if pos else 0}]")
    if pos:
        for p in pos:
            print(f"#{p.ticket}: {p.symbol} {'BUY' if p.type==0 else 'SELL'} {p.volume} @ {p.price_open} | Current: {p.price_current} | PnL: ${p.profit:+.2f}")

    mt5.shutdown()

if __name__ == "__main__":
    check_gold_target()
