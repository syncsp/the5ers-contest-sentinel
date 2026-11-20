import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime

def detailed_analysis():
    if not mt5.initialize():
        print("MT5 init failed")
        return

    symbol = "XAUUSD"
    tick = mt5.symbol_info_tick(symbol)
    print(f"LIVE TICK: Bid={tick.bid:.2f}, Ask={tick.ask:.2f}, Time={datetime.fromtimestamp(tick.time)}")

    # Pull M15, M5, M1
    r_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 30)
    df_m15 = pd.DataFrame(r_m15)
    df_m15['datetime'] = pd.to_datetime(df_m15['time'], unit='s')

    r_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 30)
    df_m5 = pd.DataFrame(r_m5)
    df_m5['datetime'] = pd.to_datetime(df_m5['time'], unit='s')

    r_m1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 30)
    df_m1 = pd.DataFrame(r_m1)
    df_m1['datetime'] = pd.to_datetime(df_m1['time'], unit='s')

    print("\n--- RECENT M15 CANDLES (Last 10) ---")
    for _, r in df_m15.tail(10).iterrows():
        print(f"M15 {r['datetime']}: O={r['open']:.2f}, H={r['high']:.2f}, L={r['low']:.2f}, C={r['close']:.2f}, Vol={r['tick_volume']}")

    print("\n--- RECENT M5 CANDLES (Last 12) ---")
    for _, r in df_m5.tail(12).iterrows():
        print(f"M5 {r['datetime']}: O={r['open']:.2f}, H={r['high']:.2f}, L={r['low']:.2f}, C={r['close']:.2f}, Vol={r['tick_volume']}")

    print("\n--- RECENT M1 CANDLES (Last 10) ---")
    for _, r in df_m1.tail(10).iterrows():
        print(f"M1 {r['datetime']}: O={r['open']:.2f}, H={r['high']:.2f}, L={r['low']:.2f}, C={r['close']:.2f}, Vol={r['tick_volume']}")

    # Identify Swing Highs and Swing Lows on M5
    print("\n--- M5 SWING HIGHS & LOWS ---")
    swing_highs = []
    swing_lows = []
    for i in range(2, len(df_m5) - 2):
        # Swing high: higher than 2 previous and 2 next
        if (df_m5['high'].iloc[i] > df_m5['high'].iloc[i-1] and 
            df_m5['high'].iloc[i] > df_m5['high'].iloc[i-2] and
            df_m5['high'].iloc[i] > df_m5['high'].iloc[i+1] and
            df_m5['high'].iloc[i] > df_m5['high'].iloc[i+2]):
            swing_highs.append((df_m5['datetime'].iloc[i], df_m5['high'].iloc[i]))
            
        # Swing low: lower than 2 previous and 2 next
        if (df_m5['low'].iloc[i] < df_m5['low'].iloc[i-1] and 
            df_m5['low'].iloc[i] < df_m5['low'].iloc[i-2] and
            df_m5['low'].iloc[i] < df_m5['low'].iloc[i+1] and
            df_m5['low'].iloc[i] < df_m5['low'].iloc[i+2]):
            swing_lows.append((df_m5['datetime'].iloc[i], df_m5['low'].iloc[i]))

    print("Recent Swing Highs:")
    for t, h in swing_highs[-5:]:
        print(f"  {t} @ ${h:.2f}")

    print("Recent Swing Lows:")
    for t, l in swing_lows[-5:]:
        print(f"  {t} @ ${l:.2f}")

    mt5.shutdown()

if __name__ == "__main__":
    detailed_analysis()
