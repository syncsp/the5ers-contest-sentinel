import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

mt5.initialize()
rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 500)
if rates is not None and len(rates) > 0:
    df = pd.DataFrame(rates)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    df['day_name'] = df['dt'].dt.day_name()
    saturday_bars = df[df['day_name'] == 'Saturday']
    sunday_bars = df[df['day_name'] == 'Sunday']
    print(f"Total H1 bars analyzed: {len(df)}")
    print(f"Saturday H1 bars found: {len(saturday_bars)}")
    print(f"Sunday H1 bars found: {len(sunday_bars)}")
    if len(saturday_bars) > 0 and len(sunday_bars) > 0:
        print(">>> CONFIRMED: BTCUSD PRINTS TICKS AND TRADES 24/7 THROUGH SATURDAY AND SUNDAY! <<<")
    else:
        print(">>> Crypto may close over weekends on this server. <<<")
else:
    print("Could not retrieve rates.")
mt5.shutdown()
