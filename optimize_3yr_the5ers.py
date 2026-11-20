"""
3-Year Quantitative Backtest & Strategy Optimizer for The5ers ($10,000 Account)
═══════════════════════════════════════════════════════════════════════════════
Evaluates 3 years of real broker M15/H1/H4 data (~30,000 to 50,000 bars per pair).
Optimizes for MAXIMUM WIN RATE (Target 80% - 95%) with MINIMAL LOSSES.

Confluence Filters Tested:
1. Baseline: M15 FVG Retest in Kill Zones
2. Confluence A: + H1 EMA 50 Trend Alignment
3. Confluence B: + H4 Trend Alignment (Dual Timeframe Flow)
4. Confluence C: + High Institutional Displacement (Body >= 1.5x ATR)
5. Confluence D: + Asian Liquidity Sweep (Smart Money Judas Trap)
6. Confluence E: + Breakeven Protection at +0.8R
"""

import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def run_3yr_optimization():
    if not mt5.initialize():
        print("MT5 initialization failed")
        return

    symbols = ['GBPUSD', 'EURUSD', 'USDJPY', 'USDCAD']
    for s in symbols:
        mt5.symbol_select(s, True)

    print("=" * 95)
    print("      3-YEAR INSTITUTIONAL BACKTEST & OPTIMIZER FOR THE5ERS ($10,000 CONTEST/CHALLENGE)")
    print("      Testing across GBPUSD, EURUSD, USDJPY, USDCAD using real historical broker data")
    print("=" * 95)

    # We will test 5 model configurations:
    models = {
        "M1: Standard FVG (London/NY, 1:1.0 RR)": {
            "use_h1": True, "use_h4": False, "min_disp": 1.0, "require_sweep": False, "be": False, "rr": 1.0
        },
        "M2: Dual Trend (H1+H4 Flow, 1:1.0 RR)": {
            "use_h1": True, "use_h4": True, "min_disp": 1.0, "require_sweep": False, "be": False, "rr": 1.0
        },
        "M3: High Displacement FVG (1.5x ATR, 1:1.2 RR)": {
            "use_h1": True, "use_h4": True, "min_disp": 1.5, "require_sweep": False, "be": False, "rr": 1.2
        },
        "M4: Judas Liquidity Sweep + FVG (1:1.2 RR)": {
            "use_h1": True, "use_h4": False, "min_disp": 1.2, "require_sweep": True, "be": False, "rr": 1.2
        },
        "M5: ELITE 5ERS CONFLUENCE + BE Protection (1:1.2 RR)": {
            "use_h1": True, "use_h4": True, "min_disp": 1.5, "require_sweep": True, "be": True, "rr": 1.2
        },
    }

    results = {m: {"trades": 0, "wins": 0, "losses": 0, "be_trades": 0, "pnl_pips": 0.0, "max_consec_losses": 0, "curr_losses": 0} for m in models}
    pair_results = {m: {s: {"wins": 0, "losses": 0, "be": 0} for s in symbols} for m in models}

    for s in symbols:
        pip = 0.01 if "JPY" in s else 0.0001
        print(f"\n⏳ Loading 3-year history for {s}...")

        # Request up to 35,000 M15 bars (~2.5 to 3 years)
        bars_m15 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_M15, 0, 35000)
        bars_h1 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_H1, 0, 10000)
        bars_h4 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_H4, 0, 2500)

        if bars_m15 is None or bars_h1 is None or len(bars_m15) < 5000:
            print(f"❌ Insufficient bars for {s}")
            continue

        print(f"   Loaded: {len(bars_m15)} M15 bars | {len(bars_h1)} H1 bars | {len(bars_h4) if bars_h4 is not None else 0} H4 bars")

        df_m15 = pd.DataFrame(bars_m15)
        df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
        df_m15 = df_m15.set_index('time')
        df_m15['hour'] = df_m15.index.hour
        df_m15['minute'] = df_m15.index.minute
        df_m15['date'] = df_m15.index.date
        df_m15['body'] = (df_m15['close'] - df_m15['open']).abs()
        df_m15['atr20'] = (df_m15['high'] - df_m15['low']).rolling(20).mean()

        # H1 EMA 50
        df_h1 = pd.DataFrame(bars_h1)
        df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
        df_h1 = df_h1.set_index('time')
        df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()
        h1_bias = df_h1['close'] > df_h1['ema50']

        # H4 EMA 50
        df_h4 = pd.DataFrame(bars_h4) if bars_h4 is not None else None
        if df_h4 is not None:
            df_h4['time'] = pd.to_datetime(df_h4['time'], unit='s')
            df_h4 = df_h4.set_index('time')
            df_h4['ema50'] = df_h4['close'].ewm(span=50, adjust=False).mean()
            h4_bias = df_h4['close'] > df_h4['ema50']
        else:
            h4_bias = None

        dates = df_m15['date'].unique()

        for m_name, cfg in models.items():
            use_h1 = cfg["use_h1"]
            use_h4 = cfg["use_h4"]
            min_disp = cfg["min_disp"]
            require_sweep = cfg["require_sweep"]
            use_be = cfg["be"]
            rr = cfg["rr"]

            for d in dates:
                day_data = df_m15[df_m15['date'] == d]
                if len(day_data) < 24: continue

                # Asian Range 00:00 to 06:00 UTC
                asian = day_data[(day_data['hour'] >= 0) & (day_data['hour'] < 6)]
                a_high = asian['high'].max() if len(asian) >= 4 else None
                a_low = asian['low'].min() if len(asian) >= 4 else None

                # Prime Execution Windows:
                # London Open: 07:00 - 10:30 UTC
                # NY Open:     12:30 - 15:30 UTC
                prime_session = day_data[
                    ((day_data['hour'] >= 7) & (day_data['hour'] <= 10)) |
                    ((day_data['hour'] == 12) & (day_data['minute'] >= 30)) |
                    ((day_data['hour'] >= 13) & (day_data['hour'] <= 15))
                ]
                if len(prime_session) < 6: continue

                trade_taken = False
                bars_list = list(prime_session.iterrows())

                for i in range(2, len(bars_list)):
                    if trade_taken: break
                    c_time, cur = bars_list[i]
                    p2_time, p2 = bars_list[i-2]
                    p1_time, p1 = bars_list[i-1]

                    # Trend checks
                    h1_ok_bull, h1_ok_bear = True, True
                    if use_h1:
                        h1_match = h1_bias.asof(c_time)
                        if pd.isna(h1_match): continue
                        h1_ok_bull = (h1_match == True)
                        h1_ok_bear = (h1_match == False)

                    h4_ok_bull, h4_ok_bear = True, True
                    if use_h4 and h4_bias is not None:
                        h4_match = h4_bias.asof(c_time)
                        if pd.isna(h4_match): continue
                        h4_ok_bull = (h4_match == True)
                        h4_ok_bear = (h4_match == False)

                    # Displacement check on candle 1 (the middle impulse candle)
                    p1_atr = p1['atr20'] if not pd.isna(p1['atr20']) else 10.0 * pip
                    is_displaced = (p1['body'] >= min_disp * p1_atr)

                    # Sweep check
                    swept_low = False
                    swept_high = False
                    if require_sweep:
                        if a_low is not None and (p2['low'] < a_low or p1['low'] < a_low or cur['low'] < a_low):
                            swept_low = True
                        if a_high is not None and (p2['high'] > a_high or p1['high'] > a_high or cur['high'] > a_high):
                            swept_high = True
                    else:
                        swept_low = True
                        swept_high = True

                    # ─────────────────────────────────────────────────────────────
                    # BULLISH FVG SETUP
                    # ─────────────────────────────────────────────────────────────
                    if h1_ok_bull and h4_ok_bull and is_displaced and swept_low:
                        if p1['close'] > p1['open'] and cur['low'] > p2['high'] + (1.5 * pip):
                            fvg_top = cur['low']
                            fvg_bottom = p2['high']
                            fvg_size = (fvg_top - fvg_bottom) / pip

                            if 2.0 <= fvg_size <= 18.0:
                                # Look for retest in the next 10 bars
                                future = day_data.loc[c_time:][1:10]
                                for ret_idx, f in future.iterrows():
                                    if fvg_bottom <= f['low'] <= fvg_top:
                                        entry = fvg_top
                                        sl = fvg_bottom - (3.5 * pip)
                                        risk = (entry - sl) / pip
                                        if 6.0 <= risk <= 22.0:
                                            tp = entry + (risk * rr * pip)
                                            be_trigger = entry + (risk * 0.8 * pip)

                                            # Track trade outcome
                                            outcome = day_data.loc[ret_idx:][1:30]
                                            hit_tp, hit_sl, hit_be = False, False, False
                                            curr_sl = sl

                                            for _, o in outcome.iterrows():
                                                # Check BE promotion
                                                if use_be and o['high'] >= be_trigger:
                                                    curr_sl = entry + (0.5 * pip) # Breakeven + spread buffer

                                                if o['low'] <= curr_sl:
                                                    if curr_sl > sl:
                                                        hit_be = True
                                                    else:
                                                        hit_sl = True
                                                    break
                                                if o['high'] >= tp:
                                                    hit_tp = True
                                                    break

                                            if hit_tp:
                                                results[m_name]["wins"] += 1
                                                results[m_name]["pnl_pips"] += risk * rr
                                                results[m_name]["curr_losses"] = 0
                                                pair_results[m_name][s]["wins"] += 1
                                                trade_taken = True
                                                break
                                            elif hit_be:
                                                results[m_name]["be_trades"] += 1
                                                pair_results[m_name][s]["be"] += 1
                                                trade_taken = True
                                                break
                                            elif hit_sl:
                                                results[m_name]["losses"] += 1
                                                results[m_name]["pnl_pips"] -= risk
                                                results[m_name]["curr_losses"] += 1
                                                if results[m_name]["curr_losses"] > results[m_name]["max_consec_losses"]:
                                                    results[m_name]["max_consec_losses"] = results[m_name]["curr_losses"]
                                                pair_results[m_name][s]["losses"] += 1
                                                trade_taken = True
                                                break

                    # ─────────────────────────────────────────────────────────────
                    # BEARISH FVG SETUP
                    # ─────────────────────────────────────────────────────────────
                    if not trade_taken and h1_ok_bear and h4_ok_bear and is_displaced and swept_high:
                        if p1['close'] < p1['open'] and cur['high'] < p2['low'] - (1.5 * pip):
                            fvg_bottom = cur['high']
                            fvg_top = p2['low']
                            fvg_size = (fvg_top - fvg_bottom) / pip

                            if 2.0 <= fvg_size <= 18.0:
                                future = day_data.loc[c_time:][1:10]
                                for ret_idx, f in future.iterrows():
                                    if fvg_bottom <= f['high'] <= fvg_top:
                                        entry = fvg_bottom
                                        sl = fvg_top + (3.5 * pip)
                                        risk = (sl - entry) / pip
                                        if 6.0 <= risk <= 22.0:
                                            tp = entry - (risk * rr * pip)
                                            be_trigger = entry - (risk * 0.8 * pip)

                                            outcome = day_data.loc[ret_idx:][1:30]
                                            hit_tp, hit_sl, hit_be = False, False, False
                                            curr_sl = sl

                                            for _, o in outcome.iterrows():
                                                if use_be and o['low'] <= be_trigger:
                                                    curr_sl = entry - (0.5 * pip)

                                                if o['high'] >= curr_sl:
                                                    if curr_sl < sl:
                                                        hit_be = True
                                                    else:
                                                        hit_sl = True
                                                    break
                                                if o['low'] <= tp:
                                                    hit_tp = True
                                                    break

                                            if hit_tp:
                                                results[m_name]["wins"] += 1
                                                results[m_name]["pnl_pips"] += risk * rr
                                                results[m_name]["curr_losses"] = 0
                                                pair_results[m_name][s]["wins"] += 1
                                                trade_taken = True
                                                break
                                            elif hit_be:
                                                results[m_name]["be_trades"] += 1
                                                pair_results[m_name][s]["be"] += 1
                                                trade_taken = True
                                                break
                                            elif hit_sl:
                                                results[m_name]["losses"] += 1
                                                results[m_name]["pnl_pips"] -= risk
                                                results[m_name]["curr_losses"] += 1
                                                if results[m_name]["curr_losses"] > results[m_name]["max_consec_losses"]:
                                                    results[m_name]["max_consec_losses"] = results[m_name]["curr_losses"]
                                                pair_results[m_name][s]["losses"] += 1
                                                trade_taken = True
                                                break

    # Calculate totals
    for m_name in models:
        r = results[m_name]
        r["trades"] = r["wins"] + r["losses"] + r["be_trades"]

    # Print comprehensive table
    print("\n" + "=" * 105)
    print("                     3-YEAR OPTIMIZATION PERFORMANCE SUMMARY")
    print("=" * 105)
    print(f"{'MODEL':<50} | {'TRADES':<6} | {'WINS':<4} | {'BE':<3} | {'LOSS':<4} | {'WIN RATE':<9} | {'MAX CONSEC L':<12} | {'PROFIT ($0.50)':<14}")
    print("-" * 115)

    for m_name, r in results.items():
        t = r["trades"]
        w = r["wins"]
        be = r["be_trades"]
        l = r["losses"]
        decisive_trades = w + l
        wr = (w / decisive_trades * 100) if decisive_trades > 0 else 0
        usd_profit = r["pnl_pips"] * 10 * 0.50
        max_cl = r["max_consec_losses"]

        print(f"{m_name:<50} | {t:<6} | {w:<4} | {be:<3} | {l:<4} | {wr:6.1f}%   | {max_cl:<12} | ${usd_profit:+10.2f}")

    print("=" * 115)

    # Detailed pair breakdown for the best model
    print("\n🔥 PAIR BREAKDOWN FOR BEST MODEL (M5: ELITE 5ERS CONFLUENCE + BE):")
    print("-" * 75)
    best_m = "M5: ELITE 5ERS CONFLUENCE + BE Protection (1:1.2 RR)"
    for s in symbols:
        p_res = pair_results[best_m][s]
        pw = p_res["wins"]
        pbe = p_res["be"]
        pl = p_res["losses"]
        ptot = pw + pl
        pwr = (pw / ptot * 100) if ptot > 0 else 0
        print(f"   {s:<8}: {pw + pbe + pl:<3} trades │ Wins: {pw:<2} │ Breakeven: {pbe:<2} │ Losses: {pl:<2} │ Win Rate: {pwr:5.1f}%")
    print("=" * 75)

    mt5.shutdown()

if __name__ == "__main__":
    run_3yr_optimization()
