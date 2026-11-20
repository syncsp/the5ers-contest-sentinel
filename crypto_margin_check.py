import MetaTrader5 as mt5

mt5.initialize()
tick_btc = mt5.symbol_info_tick('BTCUSD')
tick_eth = mt5.symbol_info_tick('ETHUSD')

print(f"BTC current price: {tick_btc.ask}")
print(f"ETH current price: {tick_eth.ask}")

for lot in [0.01, 0.02, 0.05, 0.10, 0.20]:
    m_btc = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, 'BTCUSD', lot, tick_btc.ask)
    print(f"BTC {lot} Lot -> Margin: ${m_btc:.2f}")

for lot in [0.10, 0.25, 0.50, 1.00, 2.00]:
    m_eth = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, 'ETHUSD', lot, tick_eth.ask)
    print(f"ETH {lot} Lot -> Margin: ${m_eth:.2f}")

# Check check_order_margin against our free margin ($10,058)
acc = mt5.account_info()
print(f"\nAccount Free Margin: ${acc.margin_free:.2f}")

mt5.shutdown()
