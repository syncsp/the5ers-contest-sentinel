import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone

if not mt5.initialize():
    print("Failed to initialize MT5")
    exit()

acc = mt5.account_info()
print(f"================================================================")
print(f"ACCOUNT: Login={acc.login} | Server={acc.server} | Name={acc.name}")
print(f"BALANCE: ${acc.balance:.2f} | EQUITY: ${acc.equity:.2f} | MARGIN: ${acc.margin:.2f}")
print(f"FREE MARGIN: ${acc.margin_free:.2f} | PROFIT: ${acc.profit:.2f}")
print(f"================================================================")

# Check open positions
positions = mt5.positions_get()
print(f"\nACTIVE OPEN POSITIONS: {len(positions) if positions else 0}")
if positions:
    for p in positions:
        print(f"  -> Ticket #{p.ticket} | {p.symbol} | {'BUY' if p.type==0 else 'SELL'} | Vol: {p.volume} | Open: {p.price_open} | SL: {p.sl} | TP: {p.tp} | Profit: ${p.profit:.2f}")

# Deals in the last 12 hours
now = datetime.now()
deals = mt5.history_deals_get(now - timedelta(hours=12), now)
print(f"\nCLOSED DEALS TODAY (Last 12 Hours):")
if deals:
    for d in deals:
        if d.symbol:
            d_type = "BUY" if d.type == 0 else "SELL"
            reason_map = {0: "CLIENT (Manual/OS Scan)", 3: "EXPERT (EA)", 4: "SL HIT", 5: "TP HIT", 6: "SO (StopOut)"}
            r_str = reason_map.get(d.reason, f"Reason {d.reason}")
            print(f"  Deal #{d.ticket} | Order #{d.order} | {d.symbol} | {d_type} | Vol: {d.volume} | Price: {d.price} | Profit: ${d.profit:.2f} | {r_str} | Comment: '{d.comment}'")
else:
    print("  No deals found in timeframe.")

# Comprehensive Multi-Asset Market State
symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD', 'NZDUSD', 'XAUUSD', 'GBPJPY']
print(f"\n================================================================")
print(f"REAL-TIME MARKET SNAPSHOT & ICT STRUCTURE (8 ASSETS)")
print(f"Time (UTC): {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
print(f"================================================================")

for sym in symbols:
    tick = mt5.symbol_info_tick(sym)
    sinfo = mt5.symbol_info(sym)
    if not tick:
        continue
    
    # Get M15 rates
    rates_m15 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 30)
    # Get H1 rates
    rates_h1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 24)
    # Get D1 rates (last 2 days)
    rates_d1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 2)
    
    if rates_m15 is None or len(rates_m15) < 10:
        continue

    curr_price = tick.bid
    spread = round((tick.ask - tick.bid) / sinfo.point if sinfo and sinfo.point else 0, 1)

    # Daily Range
    d_high = rates_d1[-1]['high'] if rates_d1 is not None and len(rates_d1) > 0 else 0
    d_low = rates_d1[-1]['low'] if rates_d1 is not None and len(rates_d1) > 0 else 0
    d_range_pips = (d_high - d_low) / (sinfo.point * (10 if 'JPY' in sym or sym == 'XAUUSD' else 10))
    
    # Asian Session Range (00:00 - 07:00 UTC)
    # Let's inspect last 8 M15 bars
    m15_high_8 = max(r['high'] for r in rates_m15[-8:])
    m15_low_8 = min(r['low'] for r in rates_m15[-8:])
    
    # M15 Trend & Momentum
    m15_trend = "BULLISH" if rates_m15[-1]['close'] > rates_m15[-6]['open'] else "BEARISH"
    h1_trend = "BULLISH" if rates_h1 is not None and rates_h1[-1]['close'] > rates_h1[-5]['open'] else "BEARISH"
    
    # Detect nearest FVG on M15
    fvg_info = "None active"
    for i in range(len(rates_m15)-1, 2, -1):
        c_prev2 = rates_m15[i-2]
        c_prev1 = rates_m15[i-1]
        c_curr = rates_m15[i]
        # Bullish FVG
        if c_curr['low'] > c_prev2['high']:
            fvg_size = (c_curr['low'] - c_prev2['high']) / (sinfo.point * 10)
            fvg_info = f"Bullish FVG [{c_prev2['high']:.5f} - {c_curr['low']:.5f}] ({fvg_size:.1f}p)"
            break
        # Bearish FVG
        elif c_curr['high'] < c_prev2['low']:
            fvg_size = (c_prev2['low'] - c_curr['high']) / (sinfo.point * 10)
            fvg_info = f"Bearish FVG [{c_curr['high']:.5f} - {c_prev2['low']:.5f}] ({fvg_size:.1f}p)"
            break

    print(f"\n>> {sym} | Current: {curr_price:.5f} (Spread: {spread} pts)")
    print(f"   Structure: H1 {h1_trend} | M15 {m15_trend}")
    print(f"   Daily H/L: High={d_high:.5f} | Low={d_low:.5f}")
    print(f"   Recent M15 Extrema: High={m15_high_8:.5f} | Low={m15_low_8:.5f}")
    print(f"   Nearest M15 FVG: {fvg_info}")

mt5.shutdown()
