import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone, timedelta

mt5.initialize()

pairs = ['EURUSD', 'GBPUSD', 'AUDUSD']

print(f"=== DETAILED M15 / M5 / M1 STRUCTURE AT {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')} ===")

for sym in pairs:
    print(f"\n{'='*30} {sym} {'='*30}")
    tick = mt5.symbol_info_tick(sym)
    print(f"Current Price: Bid {tick.bid:.5f} | Ask {tick.ask:.5f}")
    
    # M5 structure
    rates_m5 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 15)
    df_m5 = pd.DataFrame(rates_m5)
    df_m5['time'] = pd.to_datetime(df_m5['time'], unit='s') - timedelta(hours=2)
    print("\nRecent M5 Candles (UTC):")
    for _, row in df_m5.iloc[-6:].iterrows():
        candle_type = 'BULL' if row['close'] > row['open'] else 'BEAR'
        body_pips = abs(row['close'] - row['open']) * 10000
        print(f"  {row['time'].strftime('%H:%M')} UTC | O: {row['open']:.5f} | H: {row['high']:.5f} | L: {row['low']:.5f} | C: {row['close']:.5f} | {candle_type} ({body_pips:.1f}p)")

    # M1 structure
    rates_m1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 120)
    df_m1 = pd.DataFrame(rates_m1)
    df_m1['time'] = pd.to_datetime(df_m1['time'], unit='s') - timedelta(hours=2)

    sw_high = df_m1['high'].max()
    sw_low = df_m1['low'].min()
    hi_time = df_m1.loc[df_m1['high'].idxmax()]['time']
    lo_time = df_m1.loc[df_m1['low'].idxmin()]['time']
    print(f"\nLast 2h (16:00-17:55 UTC) Range:")
    print(f"  Swing High: {sw_high:.5f} formed at {hi_time.strftime('%H:%M')} UTC")
    print(f"  Swing Low:  {sw_low:.5f} formed at {lo_time.strftime('%H:%M')} UTC")

    # M1 recent 5 candles
    print("\nRecent M1 Candles (UTC):")
    for _, row in df_m1.iloc[-5:].iterrows():
        candle_type = 'BULL' if row['close'] > row['open'] else 'BEAR'
        body_pips = abs(row['close'] - row['open']) * 10000
        print(f"  {row['time'].strftime('%H:%M')} UTC | O: {row['open']:.5f} | H: {row['high']:.5f} | L: {row['low']:.5f} | C: {row['close']:.5f} | {candle_type} ({body_pips:.1f}p)")

mt5.shutdown()
