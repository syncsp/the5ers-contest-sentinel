import MetaTrader5 as mt5
import time
from datetime import datetime

def monitor():
    if not mt5.initialize():
        return
    
    print("Monitoring XAUUSD live tick stream...")
    for _ in range(6):
        tick = mt5.symbol_info_tick("XAUUSD")
        r = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M1, 0, 1)[0]
        m5 = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M5, 0, 1)[0]
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Live: {tick.bid:.2f}/{tick.ask:.2f} | M1 H:{r['high']:.2f} L:{r['low']:.2f} C:{r['close']:.2f} | M5 H:{m5['high']:.2f} L:{m5['low']:.2f}")
        time.sleep(2)
    mt5.shutdown()

if __name__ == "__main__":
    monitor()
