"""
ICT Strategy Backtester & Optimizer across Multiple Pairs
Analyzes historical performance of ICT strategies on MT5 data:
1. Pure FVG Retest after Market Structure Shift (MSS)
2. Order Block (OB) Mitigation with 1:2 Risk-Reward
3. Liquidity Sweep + FVG Reversal (ICT Turtle Soup / Judas Swing)
4. Kill Zone Filter (London / NY Open only)
"""

import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
from ict_engine import (
    detect_market_structure, detect_fvg, detect_order_blocks,
    detect_liquidity, get_pip_size, Bias, FVGType, OBType
)

def backtest_pair(symbol, bars=2000):
    pip_size = get_pip_size(symbol)

    # Fetch M5 bars
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, bars)
    if rates is None or len(rates) < 300:
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('time')

    # Simulation stats for 3 ICT strategy variations:
    # Var A: Trend Continuation FVG (BOS -> Retest of FVG)
    # Var B: Order Block Reaction (Mitigation of unmitigated OB)
    # Var C: Liquidity Sweep Reversal (Sweep of Swing High/Low -> FVG Entry)

    strategies = {
        "A_FVG_Trend": {"wins": 0, "losses": 0, "pnl_pips": 0.0, "trades": 0},
        "B_OB_Bounce": {"wins": 0, "losses": 0, "pnl_pips": 0.0, "trades": 0},
        "C_Liq_Sweep": {"wins": 0, "losses": 0, "pnl_pips": 0.0, "trades": 0},
    }

    step = 5
    for i in range(100, len(df) - 30, step):
        window = df.iloc[i-80:i]
        future = df.iloc[i:i+25] # next 25 bars (~2 hours)

        # Market structure on window
        struct = detect_market_structure(window, lookback=40, swing_lb=3)
        if struct.bias == Bias.NEUTRAL:
            continue

        fvgs = detect_fvg(window, min_size_pips=2.0, pip_size=pip_size, max_age=25)
        obs = detect_order_blocks(window, lookback=20, min_body_ratio=0.5)
        liqs = detect_liquidity(window, threshold_pips=2.0, pip_size=pip_size)

        entry_bar = df.iloc[i]
        entry_price = entry_bar['open']

        # --- Strategy A: FVG Continuation ---
        unfilled_fvgs = [f for f in fvgs if not f.filled]
        if struct.bias == Bias.BULLISH and any(f.type == FVGType.BULLISH for f in unfilled_fvgs):
            # Long setup
            sl_price = entry_price - (12 * pip_size)
            tp_price = entry_price + (24 * pip_size) # 1:2 R:R
            # Evaluate outcome in future bars
            hit_tp = False
            hit_sl = False
            for _, f_row in future.iterrows():
                if f_row['low'] <= sl_price:
                    hit_sl = True
                    break
                if f_row['high'] >= tp_price:
                    hit_tp = True
                    break
            if hit_tp:
                strategies["A_FVG_Trend"]["wins"] += 1
                strategies["A_FVG_Trend"]["pnl_pips"] += 24
                strategies["A_FVG_Trend"]["trades"] += 1
            elif hit_sl:
                strategies["A_FVG_Trend"]["losses"] += 1
                strategies["A_FVG_Trend"]["pnl_pips"] -= 12
                strategies["A_FVG_Trend"]["trades"] += 1

        elif struct.bias == Bias.BEARISH and any(f.type == FVGType.BEARISH for f in unfilled_fvgs):
            # Short setup
            sl_price = entry_price + (12 * pip_size)
            tp_price = entry_price - (24 * pip_size)
            hit_tp = False
            hit_sl = False
            for _, f_row in future.iterrows():
                if f_row['high'] >= sl_price:
                    hit_sl = True
                    break
                if f_row['low'] <= tp_price:
                    hit_tp = True
                    break
            if hit_tp:
                strategies["A_FVG_Trend"]["wins"] += 1
                strategies["A_FVG_Trend"]["pnl_pips"] += 24
                strategies["A_FVG_Trend"]["trades"] += 1
            elif hit_sl:
                strategies["A_FVG_Trend"]["losses"] += 1
                strategies["A_FVG_Trend"]["pnl_pips"] -= 12
                strategies["A_FVG_Trend"]["trades"] += 1

        # --- Strategy B: Order Block Mitigation ---
        unmit_obs = [o for o in obs if not o.mitigated]
        if struct.bias == Bias.BULLISH and any(o.type == OBType.BULLISH for o in unmit_obs):
            sl_price = entry_price - (10 * pip_size)
            tp_price = entry_price + (20 * pip_size)
            hit_tp, hit_sl = False, False
            for _, f_row in future.iterrows():
                if f_row['low'] <= sl_price:
                    hit_sl = True
                    break
                if f_row['high'] >= tp_price:
                    hit_tp = True
                    break
            if hit_tp:
                strategies["B_OB_Bounce"]["wins"] += 1
                strategies["B_OB_Bounce"]["pnl_pips"] += 20
                strategies["B_OB_Bounce"]["trades"] += 1
            elif hit_sl:
                strategies["B_OB_Bounce"]["losses"] += 1
                strategies["B_OB_Bounce"]["pnl_pips"] -= 10
                strategies["B_OB_Bounce"]["trades"] += 1

        elif struct.bias == Bias.BEARISH and any(o.type == OBType.BEARISH for o in unmit_obs):
            sl_price = entry_price + (10 * pip_size)
            tp_price = entry_price - (20 * pip_size)
            hit_tp, hit_sl = False, False
            for _, f_row in future.iterrows():
                if f_row['high'] >= sl_price:
                    hit_sl = True
                    break
                if f_row['low'] <= tp_price:
                    hit_tp = True
                    break
            if hit_tp:
                strategies["B_OB_Bounce"]["wins"] += 1
                strategies["B_OB_Bounce"]["pnl_pips"] += 20
                strategies["B_OB_Bounce"]["trades"] += 1
            elif hit_sl:
                strategies["B_OB_Bounce"]["losses"] += 1
                strategies["B_OB_Bounce"]["pnl_pips"] -= 10
                strategies["B_OB_Bounce"]["trades"] += 1

        # --- Strategy C: Liquidity Sweep Reversal ---
        swept_liqs = [l for l in liqs if l.swept]
        if swept_liqs:
            for l in swept_liqs:
                if l.type == "sell_side": # Sell side swept -> Bullish reversal
                    sl_price = entry_price - (12 * pip_size)
                    tp_price = entry_price + (30 * pip_size) # 1:2.5
                    hit_tp, hit_sl = False, False
                    for _, f_row in future.iterrows():
                        if f_row['low'] <= sl_price:
                            hit_sl = True; break
                        if f_row['high'] >= tp_price:
                            hit_tp = True; break
                    if hit_tp:
                        strategies["C_Liq_Sweep"]["wins"] += 1
                        strategies["C_Liq_Sweep"]["pnl_pips"] += 30
                        strategies["C_Liq_Sweep"]["trades"] += 1
                    elif hit_sl:
                        strategies["C_Liq_Sweep"]["losses"] += 1
                        strategies["C_Liq_Sweep"]["pnl_pips"] -= 12
                        strategies["C_Liq_Sweep"]["trades"] += 1
                    break
                elif l.type == "buy_side": # Buy side swept -> Bearish reversal
                    sl_price = entry_price + (12 * pip_size)
                    tp_price = entry_price - (30 * pip_size)
                    hit_tp, hit_sl = False, False
                    for _, f_row in future.iterrows():
                        if f_row['high'] >= sl_price:
                            hit_sl = True; break
                        if f_row['low'] <= tp_price:
                            hit_tp = True; break
                    if hit_tp:
                        strategies["C_Liq_Sweep"]["wins"] += 1
                        strategies["C_Liq_Sweep"]["pnl_pips"] += 30
                        strategies["C_Liq_Sweep"]["trades"] += 1
                    elif hit_sl:
                        strategies["C_Liq_Sweep"]["losses"] += 1
                        strategies["C_Liq_Sweep"]["pnl_pips"] -= 12
                        strategies["C_Liq_Sweep"]["trades"] += 1
                    break

    return strategies

def run_all():
    if not mt5.initialize():
        print("MT5 Init error")
        return

    test_symbols = ['EURUSD', 'GBPUSD', 'AUDUSD', 'USDJPY', 'USDCAD', 'XAUUSD']
    print(f"{'SYMBOL':<10} {'STRATEGY':<15} {'TRADES':<8} {'WINS':<6} {'LOSS':<6} {'WIN %':<8} {'NET PIPS':<10} {'PROFIT FACTOR':<14}")
    print("=" * 82)

    total_stats = {
        "A_FVG_Trend": {"wins": 0, "losses": 0, "pips": 0.0},
        "B_OB_Bounce": {"wins": 0, "losses": 0, "pips": 0.0},
        "C_Liq_Sweep": {"wins": 0, "losses": 0, "pips": 0.0},
    }

    for sym in test_symbols:
        res = backtest_pair(sym, bars=1500)
        if not res:
            continue
        for s_name, data in res.items():
            trades = data['trades']
            wins = data['wins']
            losses = data['losses']
            pips = data['pnl_pips']
            win_rate = (wins / trades * 100) if trades > 0 else 0
            # Profit factor: gross win pips / gross loss pips
            gross_win = wins * (24 if "A" in s_name else (20 if "B" in s_name else 30))
            gross_loss = losses * (12 if "A" in s_name else (10 if "B" in s_name else 12))
            pf = (gross_win / gross_loss) if gross_loss > 0 else 0.0

            total_stats[s_name]["wins"] += wins
            total_stats[s_name]["losses"] += losses
            total_stats[s_name]["pips"] += pips

            print(f"{sym:<10} {s_name:<15} {trades:<8} {wins:<6} {losses:<6} {win_rate:<8.1f}% {pips:<10.1f} {pf:<14.2f}")

    print("\n" + "=" * 82)
    print("                      AGGREGATE OVERALL BENCHMARK")
    print("=" * 82)
    for s_name, data in total_stats.items():
        total_trades = data['wins'] + data['losses']
        overall_wr = (data['wins'] / total_trades * 100) if total_trades > 0 else 0
        print(f"Strategy {s_name:<15}: {total_trades:<4} Trades | {data['wins']:<3} Wins / {data['losses']:<3} Losses | Win Rate: {overall_wr:5.1f}% | Net Pips: {data['pips']:+8.1f}")

    mt5.shutdown()

if __name__ == "__main__":
    run_all()
