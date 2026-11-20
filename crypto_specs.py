import MetaTrader5 as mt5

mt5.initialize()
for sym in ['BTCUSD', 'ETHUSD']:
    s = mt5.symbol_info(sym)
    tick = mt5.symbol_info_tick(sym)
    print(f"=== {sym} Specifications ===")
    print(f"  Point: {s.point}")
    print(f"  Digits: {s.digits}")
    print(f"  Contract size: {s.trade_contract_size}")
    print(f"  Min Lot: {s.volume_min} | Max Lot: {s.volume_max} | Step: {s.volume_step}")
    # Margin required for 1.0 lot
    # order_calc_margin(action, symbol, volume, price)
    margin_1lot = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, sym, 1.0, tick.ask if tick else 50000.0)
    profit_100pts = mt5.order_calc_profit(mt5.ORDER_TYPE_BUY, sym, 1.0, 50000.0, 50100.0)
    print(f"  Margin for 1.0 lot: ${margin_1lot:.2f} USD")
    print(f"  Profit for $100 price move on 1.0 lot: ${profit_100pts:.2f} USD")
    # For $175 risk:
    # If SL is $250 move on BTC: lot = 175 / 250 = 0.70 lot!
mt5.shutdown()
