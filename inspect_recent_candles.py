import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone

mt5.initialize()

def get_pip(symbol):
    if "XAU" in symbol.upper():
        return 0.1
    return 0.01 if "JPY" in symbol.upper() else 0.0001

def inspect_recent_candles(symbol):
    pip = get_pip(symbol)
    rates_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 16)
    rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 24)
    df_m15 = pd.DataFrame(rates_m15)
    df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s', utc=True)
    df_m5 = pd.DataFrame(rates_m5)
    df_m5['time'] = pd.to_datetime(df_m5['time'], unit='s', utc=True)
    
    print(f"================ {symbol} ================")
    print("Recent M15 Candles (last 6):")
    for idx, row in df_m15.tail(6).iterrows():
        body = abs(row['close'] - row['open']) / pip
        total_range = (row['high'] - row['low']) / pip
        direction = "BULL" if row['close'] > row['open'] else "BEAR"
        print(f"  {row['time'].strftime('%H:%M')} | {direction} | Open: {row['open']} Close: {row['close']} High: {row['high']} Low: {row['low']} | Body: {body:.1f}p Range: {total_range:.1f}p")
        
    print("\nRecent M5 Candles (last 6):")
    for idx, row in df_m5.tail(6).iterrows():
        body = abs(row['close'] - row['open']) / pip
        total_range = (row['high'] - row['low']) / pip
        direction = "BULL" if row['close'] > row['open'] else "BEAR"
        print(f"  {row['time'].strftime('%H:%M')} | {direction} | Open: {row['open']} Close: {row['close']} High: {row['high']} Low: {row['low']} | Body: {body:.1f}p Range: {total_range:.1f}p")
    print("")

for s in ['USDJPY', 'GBPJPY', 'USDCAD', 'NZDUSD']:
    inspect_recent_candles(s)
