import MetaTrader5 as mt5

if not mt5.initialize():
    print("Failed to initialize MT5")
    exit()

symbols = mt5.symbols_get()
print(f"Total symbols available on broker: {len(symbols) if symbols else 0}")

crypto_matches = []
if symbols:
    for s in symbols:
        name = s.name.upper()
        if any(c in name for c in ['BTC', 'ETH', 'CRYPTO', 'SOL', 'XRP', 'COIN']):
            crypto_matches.append(s)

print(f"\nCrypto symbols found ({len(crypto_matches)}):")
for cs in crypto_matches:
    # Select symbol so we can fetch tick
    mt5.symbol_select(cs.name, True)
    tick = mt5.symbol_info_tick(cs.name)
    sinfo = mt5.symbol_info(cs.name)
    trade_modes = {0: 'DISABLED', 1: 'LONG_ONLY', 2: 'SHORT_ONLY', 3: 'CLOSE_ONLY', 4: 'FULL_ACCESS'}
    t_mode_str = trade_modes.get(sinfo.trade_mode if sinfo else -1, 'N/A')
    
    bid = tick.bid if tick else 0.0
    ask = tick.ask if tick else 0.0
    
    print(f"  Symbol: {cs.name:<12} | Path: {cs.path:<25} | Trade Mode: {t_mode_str:<12} | Bid: {bid} | Ask: {ask}")

# Also check weekend trading sessions for BTCUSD if present
for cs in crypto_matches:
    if 'BTC' in cs.name.upper():
        print(f"\nExamining trading sessions for {cs.name}:")
        # Check day-of-week sessions (0=Sunday, 1=Monday, ..., 5=Friday, 6=Saturday)
        for day in range(7):
            day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
            # mt5 doesn't have a direct session api in python, but we can check if ticks or rates exist on weekends or check symbol info
        print(f"  Contract Size: {cs.trade_contract_size}")
        print(f"  Min Volume: {cs.volume_min} | Max Volume: {cs.volume_max} | Step: {cs.volume_step}")
        print(f"  Trade Calc Mode: {cs.trade_calc_mode}")

mt5.shutdown()
