import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

def check_fvg():
    if not mt5.initialize():
        return

    symbol = "XAUUSD"
    # Pull M1 bars
    r_m1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 40)
    df_m1 = pd.DataFrame(r_m1)
    df_m1['datetime'] = pd.to_datetime(df_m1['time'], unit='s')

    print("=== M1 BARS (19:30 to now) ===")
    for _, r in df_m1.tail(25).iterrows():
        print(f"M1 {r['datetime']}: O={r['open']:.2f}, H={r['high']:.2f}, L={r['low']:.2f}, C={r['close']:.2f}")

    print("\n=== M1 FVGs formed in last 25 bars ===")
    for i in range(len(df_m1) - 20, len(df_m1) - 1):
        c1 = df_m1.iloc[i - 2]
        c2 = df_m1.iloc[i - 1]
        c3 = df_m1.iloc[i]
        
        # Bullish FVG
        if c3['low'] > c1['high']:
            fvg_top = c3['low']
            fvg_bottom = c1['high']
            future = df_m1.iloc[i:]
            mitigated = (future['low'] <= fvg_bottom).any()
            status = "MITIGATED" if mitigated else "UNMITIGATED ★"
            print(f"M1 BULLISH FVG @ {c2['datetime']}: ${fvg_bottom:.2f} - ${fvg_top:.2f} (Size: ${fvg_top - fvg_bottom:.2f}) -> {status}")

        # Bearish FVG
        if c3['high'] < c1['low']:
            fvg_top = c1['low']
            fvg_bottom = c3['high']
            future = df_m1.iloc[i:]
            mitigated = (future['high'] >= fvg_top).any()
            status = "MITIGATED" if mitigated else "UNMITIGATED ★"
            print(f"M1 BEARISH FVG @ {c2['datetime']}: ${fvg_bottom:.2f} - ${fvg_top:.2f} (Size: ${fvg_top - fvg_bottom:.2f}) -> {status}")

    # Check order book / market depth or tick spread
    tick = mt5.symbol_info_tick(symbol)
    print(f"\nLive Tick: Bid={tick.bid:.2f}, Ask={tick.ask:.2f}")

    mt5.shutdown()

if __name__ == "__main__":
    check_fvg()
