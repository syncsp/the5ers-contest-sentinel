"""
ICT Market Scanner & Scalp Execution
"""

import sys
import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from ict_engine import (
    detect_market_structure, detect_fvg, detect_order_blocks,
    detect_liquidity, score_setup, get_pip_size, Bias
)

def run_scan():
    if not mt5.initialize():
        print(f"MT5 Init Error: {mt5.last_error()}")
        return

    info = mt5.account_info()
    if not info:
        print("Failed to get account info")
        mt5.shutdown()
        return

    print("=" * 65)
    print(f"ACCOUNT: {info.login} | SERVER: {info.server}")
    print(f"BALANCE: {info.balance} {info.currency} | EQUITY: {info.equity} {info.currency}")
    print(f"ALGO TRADING ENABLED (TERMINAL): {info.trade_expert}")
    print("=" * 65)

    symbols = [
        'EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'GBPJPY', 'EURJPY',
        'USDCAD', 'AUDUSD', 'USDCHF', 'EURGBP', 'NZDUSD', 'AUDCAD',
        'AUDCHF', 'AUDJPY', 'EURCHF', 'EURNZD', 'EURCAD', 'GBPCHF',
        'GBPAUD', 'GBPCAD', 'GBPNZD', 'CADJPY', 'CHFJPY', 'AUDNZD'
    ]

    results = []

    for symbol in symbols:
        pip_size = get_pip_size(symbol)

        # 1. Higher Timeframe (H1/H4 for bias)
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
        if rates_h1 is None or len(rates_h1) < 50:
            continue
        df_h1 = pd.DataFrame(rates_h1)
        df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
        df_h1 = df_h1.set_index('time')
        htf = detect_market_structure(df_h1, lookback=50, swing_lb=4)

        if htf.bias == Bias.NEUTRAL:
            continue

        # 2. Lower Timeframe (M5 for scalping)
        rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
        if rates_m5 is None or len(rates_m5) < 50:
            continue
        df_m5 = pd.DataFrame(rates_m5)
        df_m5['time'] = pd.to_datetime(df_m5['time'], unit='s')
        df_m5 = df_m5.set_index('time')
        ltf = detect_market_structure(df_m5, lookback=30, swing_lb=3)

        direction = "BUY" if htf.bias == Bias.BULLISH else "SELL"
        aligned = (ltf.bias == htf.bias)

        fvgs = detect_fvg(df_m5, min_size_pips=2.0, pip_size=pip_size, max_age=30)
        obs = detect_order_blocks(df_m5, lookback=20, min_body_ratio=0.5)
        liq = detect_liquidity(df_m5, threshold_pips=2.0, pip_size=pip_size)

        score = score_setup(htf, fvgs, obs, liq, direction)

        tick = mt5.symbol_info_tick(symbol)
        price = tick.bid if tick else 0.0

        results.append({
            'symbol': symbol,
            'htf': htf.bias.value.upper(),
            'ltf': ltf.bias.value.upper(),
            'aligned': aligned,
            'direction': direction,
            'score': score,
            'fvgs': len([f for f in fvgs if not f.filled]),
            'obs': len([o for o in obs if not o.mitigated]),
            'price': price,
            'df_m5': df_m5,
            'fvgs_list': fvgs,
            'obs_list': obs,
            'pip_size': pip_size
        })

    # Sort results
    results.sort(key=lambda x: (x['aligned'], x['score']), reverse=True)

    print(f"\n{'SYMBOL':<10} {'HTF':<9} {'LTF':<9} {'ALIGNED':<9} {'DIR':<6} {'SCORE':<7} {'UNFILLED FVG':<14} {'PRICE':<12}")
    print("-" * 80)
    for r in results:
        flag = "🔥" if (r['aligned'] and r['score'] >= 50) else "  "
        print(f"{flag} {r['symbol']:<8} {r['htf']:<9} {r['ltf']:<9} {str(r['aligned']):<9} {r['direction']:<6} {r['score']:<7.0f} {r['fvgs']:<14} {r['price']:<12.5f}")

    return results

if __name__ == "__main__":
    run_scan()
    mt5.shutdown()
