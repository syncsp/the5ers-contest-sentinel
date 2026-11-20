import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime

def live_gold_audit():
    if not mt5.initialize():
        print("MT5 initialization failed")
        return

    symbol = "XAUUSD"
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print("Failed to get tick")
        return
        
    server_time = datetime.fromtimestamp(tick.time)
    print("=" * 65)
    print(f"  ACTIVE XAUUSD INSTITUTIONAL LIVE STREAM [{server_time}]")
    print(f"  Bid: {tick.bid:.2f} | Ask: {tick.ask:.2f} | Spread: ${(tick.ask - tick.bid):.2f}")
    print("=" * 65)

    # 1. Pull M5, M15, H1
    r_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 20)
    df_m5 = pd.DataFrame(r_m5)
    df_m5['datetime'] = pd.to_datetime(df_m5['time'], unit='s')

    r_m1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 15)
    df_m1 = pd.DataFrame(r_m1)
    df_m1['datetime'] = pd.to_datetime(df_m1['time'], unit='s')

    print("\n--- [1] RECENT M5 MARKET STRUCTURE (Last 8 Bars) ---")
    for _, r in df_m5.tail(8).iterrows():
        delta = r['close'] - r['open']
        bias = "BEARISH ▼" if delta < 0 else "BULLISH ▲"
        print(f"M5 {r['datetime']} | O:{r['open']:.2f} H:{r['high']:.2f} L:{r['low']:.2f} C:{r['close']:.2f} | {bias} (${delta:+.2f}) | Vol: {r['tick_volume']}")

    print("\n--- [2] RECENT M1 CANDLE ACTION (Last 8 Bars) ---")
    for _, r in df_m1.tail(8).iterrows():
        print(f"M1 {r['datetime']} | O:{r['open']:.2f} H:{r['high']:.2f} L:{r['low']:.2f} C:{r['close']:.2f} | Vol: {r['tick_volume']}")

    # 2. Check current swing highs and lows
    curr_price = tick.bid
    m5_recent_high = df_m5['high'].tail(12).max()
    m5_recent_low = df_m5['low'].tail(12).min()
    print(f"\n--- [3] IMMEDIATE M5 LIQUIDITY RANGE ---")
    print(f"  • M5 Range High: ${m5_recent_high:.2f} (Distance: +${m5_recent_high - curr_price:.2f})")
    print(f"  • M5 Range Low:  ${m5_recent_low:.2f} (Distance: -${curr_price - m5_recent_low:.2f})")
    print(f"  • Asian Low SSL: $3514.51 (Distance: -${curr_price - 3514.51:.2f})")
    print(f"  • Macro Level:   $3500.00 (Distance: -${curr_price - 3500.00:.2f})")

    # 3. Precision 1:2 and 1:3 RR Roadmaps targeting $3514.51 and $3500.00
    print("\n--- [4] PRECISION 1:2 & 1:3 RR INSTITUTIONAL ROADMAPS ---")
    print("Fixed Risk Budget: $75.00 USD (0.75% of $10,000)")
    print("Contract: 1.00 Lot = 100 oz ($1.00 move = $100.00 / lot)")

    # Target 1: Asian Low $3514.51
    # Target 2: Round Number $3500.00
    targets = [
        {"name": "Asian Low SSL Sweep", "tp": 3514.51},
        {"name": "Round Number $3500 Macro", "tp": 3500.00}
    ]

    # Model setups from different potential entry points:
    # A: Market Entry / Immediate Continuation
    # B: Pullback Entry into M5 Supply ($3528.50 - $3530.00)
    entries = [
        {"desc": "Market Execution (Current Price)", "entry": curr_price},
        {"desc": "Pullback into M5 Breaker / Supply", "entry": 3528.50},
        {"desc": "Deep Retest of $3530 Psychological", "entry": 3530.00}
    ]

    for ent in entries:
        e = ent["entry"]
        print(f"\n>>> SCENARIO: {ent['desc']} (Entry: ${e:.2f})")
        for tgt in targets:
            tp = tgt["tp"]
            reward_dist = e - tp
            if reward_dist <= 0:
                continue

            # For 1:2 RR: SL dist = reward_dist / 2.0
            sl_dist_1_2 = reward_dist / 2.0
            sl_price_1_2 = e + sl_dist_1_2
            lot_1_2 = round(75.0 / (sl_dist_1_2 * 100.0), 2)
            actual_risk_1_2 = lot_1_2 * sl_dist_1_2 * 100.0
            actual_reward_1_2 = lot_1_2 * reward_dist * 100.0

            # For 1:3 RR: SL dist = reward_dist / 3.0
            sl_dist_1_3 = reward_dist / 3.0
            sl_price_1_3 = e + sl_dist_1_3
            lot_1_3 = round(75.0 / (sl_dist_1_3 * 100.0), 2)
            actual_risk_1_3 = lot_1_3 * sl_dist_1_3 * 100.0
            actual_reward_1_3 = lot_1_3 * reward_dist * 100.0

            print(f"  Target: {tgt['name']} (${tp:.2f}) | Total Move: ${reward_dist:.2f}")
            print(f"    [1:2 RR] SL: ${sl_price_1_2:.2f} (Dist: ${sl_dist_1_2:.2f}) | Lot: {lot_1_2:.2f} | Risk: ${actual_risk_1_2:.2f} | Reward: ${actual_reward_1_2:.2f}")
            print(f"    [1:3 RR] SL: ${sl_price_1_3:.2f} (Dist: ${sl_dist_1_3:.2f}) | Lot: {lot_1_3:.2f} | Risk: ${actual_risk_1_3:.2f} | Reward: ${actual_reward_1_3:.2f}")

    # 4. Check Open Position on GBPUSD
    pos = mt5.positions_get()
    print("\n--- [5] LIVE ACCOUNT PORTFOLIO STATUS ---")
    if pos:
        for p in pos:
            pnl = p.profit
            print(f"  Active Position: #{p.ticket} | {p.symbol} {'BUY' if p.type==0 else 'SELL'} {p.volume} lots | Entry: {p.price_open:.5f} | Current: {p.price_current:.5f} | PnL: ${pnl:+.2f}")
    else:
        print("  Zero open positions. Ready for deployment.")

    mt5.shutdown()

if __name__ == "__main__":
    live_gold_audit()
