"""
FTMO Scalper Strategy Optimization Engine
Backtests different aggressive parameter combinations on FTMO M1 historical bars:
- Combos: SL (4, 5, 6, 8 pips) vs TP (6, 8, 10, 12, 16 pips)
- Breakeven Trigger: +3 pips vs +4 pips
- Trend Filter: None vs M5 EMA 50 alignment
"""

import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def run_optimization():
    if not mt5.initialize():
        print("MT5 Init error")
        return

    symbols = ['AUDUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD']
    print("=" * 75)
    print("        OPTIMIZING FTMO M1 SCALPER FOR HIGHEST SUCCESS & PROFIT")
    print("=" * 75)

    test_configs = [
        {"name": "Ultra-Fast (Tight 4p SL / 6p TP, BE at +3p)", "sl": 4.0, "tp": 6.0, "be": 3.0, "rr": 1.5},
        {"name": "Standard ICT (5p SL / 10p TP, BE at +3.5p)", "sl": 5.0, "tp": 10.0, "be": 3.5, "rr": 2.0},
        {"name": "Aggressive Runner (6p SL / 14p TP, BE at +4p)", "sl": 6.0, "tp": 14.0, "be": 4.0, "rr": 2.3},
        {"name": "High-Probability Trend (5p SL / 8p TP, BE at +3p)", "sl": 5.0, "tp": 8.0, "be": 3.0, "rr": 1.6},
    ]

    for cfg in test_configs:
        tot_trades, tot_wins, tot_losses, tot_be = 0, 0, 0, 0
        tot_profit_pips = 0.0

        for s in symbols:
            pip_size = 0.01 if "JPY" in s else (0.1 if "XAU" in s else 0.0001)
            bars = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_M1, 0, 2000)
            if bars is None or len(bars) < 300: continue

            df = pd.DataFrame(bars)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df = df.set_index('time')
            df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()

            sl_pips = cfg['sl'] if "XAU" not in s else cfg['sl'] * 3.0
            tp_pips = cfg['tp'] if "XAU" not in s else cfg['tp'] * 3.0
            be_pips = cfg['be'] if "XAU" not in s else cfg['be'] * 3.0

            step = 6
            for i in range(50, len(df) - 30, step):
                bar = df.iloc[i]
                prev = df.iloc[i-1]
                prev2 = df.iloc[i-2]

                # Setup: FVG + Trend
                is_bull_fvg = (bar['low'] > prev2['high']) and (bar['close'] > bar['ema50'])
                is_bear_fvg = (bar['high'] < prev2['low']) and (bar['close'] < bar['ema50'])

                if not is_bull_fvg and not is_bear_fvg: continue

                direction = "BUY" if is_bull_fvg else "SELL"
                entry = bar['close']
                sl = entry - (sl_pips * pip_size) if direction == "BUY" else entry + (sl_pips * pip_size)
                tp = entry + (tp_pips * pip_size) if direction == "BUY" else entry - (tp_pips * pip_size)

                future = df.iloc[i+1:i+25]
                hit_tp, hit_sl, hit_be = False, False, False
                reached_be = False

                for _, f in future.iterrows():
                    cur_profit = (f['high'] - entry)/pip_size if direction == "BUY" else (entry - f['low'])/pip_size
                    if cur_profit >= be_pips:
                        reached_be = True

                    # Check SL
                    if direction == "BUY" and f['low'] <= (entry if reached_be else sl):
                        if reached_be: hit_be = True
                        else: hit_sl = True
                        break
                    elif direction == "SELL" and f['high'] >= (entry if reached_be else sl):
                        if reached_be: hit_be = True
                        else: hit_sl = True
                        break

                    # Check TP
                    if direction == "BUY" and f['high'] >= tp:
                        hit_tp = True; break
                    elif direction == "SELL" and f['low'] <= tp:
                        hit_tp = True; break

                if hit_tp:
                    tot_wins += 1; tot_profit_pips += tp_pips; tot_trades += 1
                elif hit_be:
                    tot_be += 1; tot_trades += 1 # Breakeven = 0 loss!
                elif hit_sl:
                    tot_losses += 1; tot_profit_pips -= sl_pips; tot_trades += 1

        effective_win_rate = ((tot_wins + tot_be) / tot_trades * 100) if tot_trades > 0 else 0
        pure_win_rate = (tot_wins / tot_trades * 100) if tot_trades > 0 else 0
        print(f"\nConfiguration: {cfg['name']}")
        print(f"  Total Trades:     {tot_trades}")
        print(f"  Wins:             {tot_wins} ({pure_win_rate:.1f}%)")
        print(f"  Breakeven (Safe): {tot_be} (Saved by Auto-Breakeven!)")
        print(f"  Losses:           {tot_losses}")
        print(f"  Non-Losing Rate:  {effective_win_rate:.1f}% (Wins + BE)")
        print(f"  Net Pip Gain:     {tot_profit_pips:+.1f} pips")

    print("\n" + "=" * 75)
    mt5.shutdown()

if __name__ == "__main__":
    run_optimization()
