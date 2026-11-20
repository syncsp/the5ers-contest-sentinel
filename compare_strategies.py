"""
Comprehensive Quantitative Backtest: Finding the Highest Win-Rate Strategy
══════════════════════════════════════════════════════════════════════════════
Analyzes multiple institutional strategies over 4,000 M15 bars (~6 months)
across Forex Majors to find the exact setup with the highest win rate and profit.
"""

import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def run_multi_strategy_backtest():
    if not mt5.initialize():
        print("Failed to initialize MT5")
        return

    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD']
    for s in symbols:
        mt5.symbol_select(s, True)

    print("=" * 85)
    print("      QUANTITATIVE BACKTEST: HIGHEST WIN-RATE INSTITUTIONAL SETUPS")
    print("      Testing 4,000 M15 bars per pair (~6 months of real broker data)")
    print("=" * 85)

    # Strategy 1: Asian Sweep + Daily Bias (1:1.2 RR) - Fast Target, High Win Rate
    # Strategy 2: Asian Sweep + Daily Bias (1:1.5 RR) - Balanced
    # Strategy 3: Asian Sweep + Daily Bias (1:2.0 RR) - Classic ICT
    # Strategy 4: London Open Momentum Breakout + 1:1.2 RR
    # Strategy 5: M15 FVG Retest in London/NY Kill Zones (1:1.5 RR)

    strategies = {
        "1. Asian Sweep + D1 Bias (1:1.2 RR)": {"type": "asian_sweep", "rr": 1.2, "use_d1": True},
        "2. Asian Sweep + D1 Bias (1:1.5 RR)": {"type": "asian_sweep", "rr": 1.5, "use_d1": True},
        "3. Asian Sweep + D1 Bias (1:2.0 RR)": {"type": "asian_sweep", "rr": 2.0, "use_d1": True},
        "4. Pure Asian Sweep Reversal (1:1.2 RR)": {"type": "asian_sweep", "rr": 1.2, "use_d1": False},
        "5. London Kill Zone FVG Retest (1:1.5 RR)": {"type": "fvg_retest", "rr": 1.5, "use_d1": True},
    }

    results = {name: {"trades": 0, "wins": 0, "losses": 0, "pnl_pips": 0.0, "max_dd_trades": 0, "current_dd": 0} for name in strategies}

    for strat_name, cfg in strategies.items():
        rr = cfg["rr"]
        strat_type = cfg["type"]
        use_d1 = cfg["use_d1"]

        for s in symbols:
            pip = 0.01 if "JPY" in s else 0.0001
            bars_m15 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_M15, 0, 4000)
            bars_d1 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_D1, 0, 100)
            if bars_m15 is None or len(bars_m15) < 500 or bars_d1 is None:
                continue

            df_m15 = pd.DataFrame(bars_m15)
            df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
            df_m15 = df_m15.set_index('time')
            df_m15['hour'] = df_m15.index.hour
            df_m15['date'] = df_m15.index.date

            # D1 EMA 20
            df_d1 = pd.DataFrame(bars_d1)
            df_d1['time'] = pd.to_datetime(df_d1['time'], unit='s')
            df_d1 = df_d1.set_index('time')
            df_d1['ema20'] = df_d1['close'].ewm(span=20, adjust=False).mean()
            df_d1['date'] = df_d1.index.date
            d1_bias_map = dict(zip(df_d1['date'], df_d1['close'] > df_d1['ema20']))

            dates = df_m15['date'].unique()

            for d in dates:
                if use_d1 and d not in d1_bias_map:
                    continue
                d1_bull = d1_bias_map[d] if use_d1 else None

                day_data = df_m15[df_m15['date'] == d]
                if len(day_data) < 20: continue

                if strat_type == "asian_sweep":
                    # Asian range 00:00 to 06:00
                    asian = day_data[(day_data['hour'] >= 0) & (day_data['hour'] < 6)]
                    if len(asian) < 4: continue
                    a_high = asian['high'].max()
                    a_low = asian['low'].min()
                    a_range_pips = (a_high - a_low) / pip

                    # Asian range filter (must not be too huge > 45 pips or too tight < 10 pips)
                    if not (10.0 <= a_range_pips <= 45.0): continue

                    # Trade window: London Open (07:00 - 11:00 UTC)
                    window = day_data[(day_data['hour'] >= 7) & (day_data['hour'] <= 11)]
                    if len(window) < 4: continue

                    trade_executed = False
                    for idx, bar in window.iterrows():
                        if trade_executed: break

                        # BUY Condition: Low swept Asian Low and closed back inside
                        can_buy = (d1_bull is True) if use_d1 else True
                        if can_buy and bar['low'] < a_low and bar['close'] > a_low:
                            entry = bar['close']
                            sl = bar['low'] - (3.0 * pip)
                            risk = (entry - sl) / pip
                            if 8.0 <= risk <= 25.0:
                                tp = entry + (risk * rr * pip)
                                future = day_data.loc[idx:][1:30]
                                hit_tp, hit_sl = False, False
                                for _, f in future.iterrows():
                                    if f['low'] <= sl: hit_sl = True; break
                                    if f['high'] >= tp: hit_tp = True; break

                                if hit_tp:
                                    results[strat_name]["wins"] += 1
                                    results[strat_name]["pnl_pips"] += risk * rr
                                    results[strat_name]["current_dd"] = 0
                                    trade_executed = True
                                elif hit_sl:
                                    results[strat_name]["losses"] += 1
                                    results[strat_name]["pnl_pips"] -= risk
                                    results[strat_name]["current_dd"] += 1
                                    if results[strat_name]["current_dd"] > results[strat_name]["max_dd_trades"]:
                                        results[strat_name]["max_dd_trades"] = results[strat_name]["current_dd"]
                                    trade_executed = True

                        # SELL Condition: High swept Asian High and closed back inside
                        can_sell = (d1_bull is False) if use_d1 else True
                        if not trade_executed and can_sell and bar['high'] > a_high and bar['close'] < a_high:
                            entry = bar['close']
                            sl = bar['high'] + (3.0 * pip)
                            risk = (sl - entry) / pip
                            if 8.0 <= risk <= 25.0:
                                tp = entry - (risk * rr * pip)
                                future = day_data.loc[idx:][1:30]
                                hit_tp, hit_sl = False, False
                                for _, f in future.iterrows():
                                    if f['high'] >= sl: hit_sl = True; break
                                    if f['low'] <= tp: hit_tp = True; break

                                if hit_tp:
                                    results[strat_name]["wins"] += 1
                                    results[strat_name]["pnl_pips"] += risk * rr
                                    results[strat_name]["current_dd"] = 0
                                    trade_executed = True
                                elif hit_sl:
                                    results[strat_name]["losses"] += 1
                                    results[strat_name]["pnl_pips"] -= risk
                                    results[strat_name]["current_dd"] += 1
                                    if results[strat_name]["current_dd"] > results[strat_name]["max_dd_trades"]:
                                        results[strat_name]["max_dd_trades"] = results[strat_name]["current_dd"]
                                    trade_executed = True

                elif strat_type == "fvg_retest":
                    # M15 Fair Value Gap in London/NY (07:00 to 14:00)
                    session = day_data[(day_data['hour'] >= 7) & (day_data['hour'] <= 14)]
                    if len(session) < 10: continue

                    trade_executed = False
                    bars_list = list(session.iterrows())
                    for i in range(2, len(bars_list)):
                        if trade_executed: break
                        idx, cur = bars_list[i]
                        p2_idx, bar_minus_2 = bars_list[i-2]
                        p1_idx, bar_minus_1 = bars_list[i-1]

                        # Bullish FVG: Low of candle 0 > High of candle -2
                        if d1_bull and bar_minus_1['close'] > bar_minus_1['open']:
                            if cur['low'] > bar_minus_2['high'] + (2.0 * pip):
                                fvg_top = cur['low']
                                fvg_bottom = bar_minus_2['high']
                                # Retest in future bars
                                future = day_data.loc[idx:][1:16]
                                for f_idx, f in future.iterrows():
                                    if fvg_bottom <= f['low'] <= fvg_top:
                                        # Entry on retest
                                        entry = fvg_top
                                        sl = fvg_bottom - (3.0 * pip)
                                        risk = (entry - sl) / pip
                                        if 6.0 <= risk <= 20.0:
                                            tp = entry + (risk * rr * pip)
                                            after_entry = day_data.loc[f_idx:][1:25]
                                            hit_tp, hit_sl = False, False
                                            for _, a in after_entry.iterrows():
                                                if a['low'] <= sl: hit_sl = True; break
                                                if a['high'] >= tp: hit_tp = True; break

                                            if hit_tp:
                                                results[strat_name]["wins"] += 1
                                                results[strat_name]["pnl_pips"] += risk * rr
                                                trade_executed = True; break
                                            elif hit_sl:
                                                results[strat_name]["losses"] += 1
                                                results[strat_name]["pnl_pips"] -= risk
                                                trade_executed = True; break

                        # Bearish FVG: High of candle 0 < Low of candle -2
                        elif not d1_bull and bar_minus_1['close'] < bar_minus_1['open']:
                            if cur['high'] < bar_minus_2['low'] - (2.0 * pip):
                                fvg_bottom = cur['high']
                                fvg_top = bar_minus_2['low']
                                future = day_data.loc[idx:][1:16]
                                for f_idx, f in future.iterrows():
                                    if fvg_bottom <= f['high'] <= fvg_top:
                                        entry = fvg_bottom
                                        sl = fvg_top + (3.0 * pip)
                                        risk = (sl - entry) / pip
                                        if 6.0 <= risk <= 20.0:
                                            tp = entry - (risk * rr * pip)
                                            after_entry = day_data.loc[f_idx:][1:25]
                                            hit_tp, hit_sl = False, False
                                            for _, a in after_entry.iterrows():
                                                if a['high'] >= sl: hit_sl = True; break
                                                if a['low'] <= tp: hit_tp = True; break

                                            if hit_tp:
                                                results[strat_name]["wins"] += 1
                                                results[strat_name]["pnl_pips"] += risk * rr
                                                trade_executed = True; break
                                            elif hit_sl:
                                                results[strat_name]["losses"] += 1
                                                results[strat_name]["pnl_pips"] -= risk
                                                trade_executed = True; break

        results[strat_name]["trades"] = results[strat_name]["wins"] + results[strat_name]["losses"]

    # Print summary table
    print(f"\n{'STRATEGY':<42} | {'TRADES':<6} | {'WINS':<5} | {'LOSSES':<6} | {'WIN RATE':<9} | {'NET PIPS':<9} | {'PROFIT ($0.50 LOT)':<18}")
    print("-" * 105)
    for name, r in results.items():
        t = r["trades"]
        w = r["wins"]
        l = r["losses"]
        wr = (w / t * 100) if t > 0 else 0
        pips = r["pnl_pips"]
        usd_pnl = pips * 10 * 0.50
        print(f"{name:<42} | {t:<6} | {w:<5} | {l:<6} | {wr:6.1f}%   | {pips:+8.1f}p | ${usd_pnl:+10.2f} USD")
    print("=" * 105)

    mt5.shutdown()

if __name__ == "__main__":
    run_multi_strategy_backtest()
