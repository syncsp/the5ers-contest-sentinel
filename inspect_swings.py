import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone

mt5.initialize()

def analyze_swings_and_session(symbol):
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 60)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    today = datetime.now(timezone.utc).date()
    today_bars = df[df['time'].dt.date == today]
    
    asian = today_bars[(today_bars['time'].dt.hour >= 0) & (today_bars['time'].dt.hour < 6)]
    london = today_bars[(today_bars['time'].dt.hour >= 7) & (today_bars['time'].dt.hour < 12)]
    ny = today_bars[today_bars['time'].dt.hour >= 12]
    
    a_high = asian['high'].max() if len(asian) else None
    a_low = asian['low'].min() if len(asian) else None
    l_high = london['high'].max() if len(london) else None
    l_low = london['low'].min() if len(london) else None
    ny_high = ny['high'].max() if len(ny) else None
    ny_low = ny['low'].min() if len(ny) else None
    
    last_candle = df.iloc[-1]
    
    print(f"=== {symbol} ===")
    print(f"Current Price: {last_candle['close']} (High: {last_candle['high']}, Low: {last_candle['low']})")
    print(f"Asian Range: High={a_high}, Low={a_low}")
    print(f"London Range: High={l_high}, Low={l_low}")
    print(f"NY Range: High={ny_high}, Low={ny_low}")
    print(f"Last 4 M15 closes: {df['close'].iloc[-4:].tolist()}")
    print("")

for s in ['USDJPY', 'GBPJPY', 'USDCAD', 'NZDUSD', 'AUDUSD', 'GBPUSD']:
    analyze_swings_and_session(s)
