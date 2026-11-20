import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta

mt5.initialize()
for s in ['BTCUSD', 'ETHUSD']:
    res = mt5.symbol_select(s, True)
    info = mt5.symbol_info(s)
    tick = mt5.symbol_info_tick(s)
    rates = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_M15, 0, 5)
    print(f"\n{s}:")
    print(f"  Selected: {res}")
    print(f"  Visible: {info.visible if info else 'No info'}")
    print(f"  Trade Mode: {info.trade_mode if info else 'No info'}")
    print(f"  Tick: Bid={tick.bid if tick else 'No tick'}, Ask={tick.ask if tick else 'No tick'}, Time={datetime.fromtimestamp(tick.time) if tick and tick.time else 'None'}")
    if rates is not None and len(rates) > 0:
        last_bar = rates[-1]
        bar_time = datetime.fromtimestamp(last_bar['time'])
        print(f"  Last M15 Bar: Time={bar_time}, Open={last_bar['open']}, Close={last_bar['close']}")
    else:
        print("  No M15 rates returned.")

mt5.shutdown()
