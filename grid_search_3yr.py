"""
Grid Search Optimizer: Finding the Perfect Zero-Loss / Near Zero-Loss Setup
═════════════════════════════════════════════════════════════════════════
Testing parameter variations across 35,000 bars (~3 years) on GBPUSD & EURUSD:
- R:R: 0.8, 1.0, 1.2, 1.5
- Displacement: 1.0x, 1.2x, 1.5x
- Breakeven Trigger: None, 0.7R, 0.9R
"""

import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def run_grid_search():
    if not mt5.initialize(): return

    symbols = ['GBPUSD', 'EURUSD']
    for s in symbols: mt5.symbol_select(s, True)

    print("=" * 95, flush=True)
    print("      🎯 GRID SEARCH OPTIMIZATION: GBPUSD & EURUSD (3 YEARS / 35,000 BARS)", flush=True)
    print("=" * 95, flush=True)

    grid_results = []

    # Pre-load data once
    data_store = {}
    for s in symbols:
        pip = 0.0001
        bars_m15 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_M15, 0, 35000)
        bars_h1 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_H1, 0, 10000)
        bars_h4 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_H4, 0, 2500)
        if bars_m15 is None or bars_h1 is None: continue

        df_m15 = pd.DataFrame(bars_m15)
        df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
        df_m15['hour'] = df_m15['time'].dt.hour
        df_m15['minute'] = df_m15['time'].dt.minute
        df_m15['date'] = df_m15['time'].dt.date
        df_m15['body'] = (df_m15['close'] - df_m15['open']).abs()
        df_m15['atr20'] = (df_m15['high'] - df_m15['low']).rolling(20).mean()

        df_h1 = pd.DataFrame(bars_h1)
        df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
        df_h1 = df_h1.set_index('time')
        df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()
        h1_bias = df_h1['close'] > df_h1['ema50']

        df_h4 = pd.DataFrame(bars_h4) if bars_h4 is not None else None
        if df_h4 is not None:
            df_h4['time'] = pd.to_datetime(df_h4['time'], unit='s')
            df_h4 = df_h4.set_index('time')
            df_h4['ema50'] = df_h4['close'].ewm(span=50, adjust=False).mean()
            h4_bias = df_h4['close'] > df_h4['ema50']
        else:
            h4_bias = None

        days_dict = {d: group for d, group in df_m15.groupby('date')}
        data_store[s] = {
            'pip': pip,
            'days_dict': days_dict,
            'h1_bias': h1_bias,
            'h4_bias': h4_bias
        }

    # Sweep parameters
    param_list = [
        {"name": "Conservative Scalp (0.8 RR, No BE)", "rr": 0.8, "min_disp": 1.2, "be": None},
        {"name": "True 1:1 RR Sniper (1.0 RR, No BE)", "rr": 1.0, "min_disp": 1.2, "be": None},
        {"name": "Dynamic 1:1 RR + 0.7R BE Shield",    "rr": 1.0, "min_disp": 1.2, "be": 0.7},
        {"name": "Optimal 1:1.2 RR (No BE)",           "rr": 1.2, "min_disp": 1.2, "be": None},
        {"name": "Optimal 1:1.2 RR + 0.9R BE Shield",  "rr": 1.2, "min_disp": 1.2, "be": 0.9},
        {"name": "High RR 1:1.5 (No BE)",              "rr": 1.5, "min_disp": 1.2, "be": None},
        {"name": "Ultra-Filtered (1.5x Disp, 1.0 RR)", "rr": 1.0, "min_disp": 1.5, "be": None},
        {"name": "Ultra-Filtered (1.5x Disp, 1.2 RR)", "rr": 1.2, "min_disp": 1.5, "be": None},
    ]

    for p in param_list:
        rr = p["rr"]
        min_disp = p["min_disp"]
        be_trigger_mult = p["be"]

        tot_w, tot_l, tot_be = 0, 0, 0
        tot_pips = 0.0
        max_consec_l = 0
        curr_l = 0

        for s in symbols:
            d_info = data_store[s]
            pip = d_info['pip']
            days_dict = d_info['days_dict']
            h1_bias = d_info['h1_bias']
            h4_bias = d_info['h4_bias']

            for d, day_data in days_dict.items():
                if len(day_data) < 24: continue

                prime_session = day_data[
                    ((day_data['hour'] >= 7) & (day_data['hour'] <= 10)) |
                    ((day_data['hour'] == 12) & (day_data['minute'] >= 30)) |
                    ((day_data['hour'] >= 13) & (day_data['hour'] <= 15))
                ]
                if len(prime_session) < 6: continue

                trade_done = False
                bars_list = prime_session.to_dict('records')

                for i in range(2, len(bars_list)):
                    if trade_done: break
                    cur = bars_list[i]
                    p2 = bars_list[i-2]
                    p1 = bars_list[i-1]
                    c_time = cur['time']

                    # Dual trend
                    h1_match = h1_bias.asof(c_time)
                    h4_match = h4_bias.asof(c_time) if h4_bias is not None else None
                    if pd.isna(h1_match) or pd.isna(h4_match): continue

                    p1_atr = p1['atr20'] if not pd.isna(p1['atr20']) else 10.0 * pip
                    if p1['body'] < min_disp * p1_atr: continue

                    # Bullish
                    if h1_match and h4_match and p1['close'] > p1['open']:
                        if cur['low'] > p2['high'] + (1.5 * pip):
                            fvg_top = cur['low']
                            fvg_bottom = p2['high']
                            sl = fvg_bottom - (3.5 * pip)
                            risk = (fvg_top - sl) / pip
                            if 6.0 <= risk <= 20.0:
                                future = day_data[day_data['time'] > c_time].head(10).to_dict('records')
                                for f in future:
                                    if fvg_bottom <= f['low'] <= fvg_top:
                                        entry = fvg_top
                                        tp = entry + (risk * rr * pip)
                                        be_price = entry + (risk * be_trigger_mult * pip) if be_trigger_mult else None

                                        outcome = day_data[day_data['time'] > f['time']].head(30).to_dict('records')
                                        hit_tp, hit_sl, hit_be = False, False, False
                                        curr_sl = sl

                                        for o in outcome:
                                            if be_price and o['high'] >= be_price:
                                                curr_sl = entry + (0.5 * pip)
                                            if o['low'] <= curr_sl:
                                                if curr_sl > sl: hit_be = True
                                                else: hit_sl = True
                                                break
                                            if o['high'] >= tp:
                                                hit_tp = True
                                                break

                                        if hit_tp:
                                            tot_w += 1; tot_pips += risk * rr; curr_l = 0; trade_done = True; break
                                        elif hit_be:
                                            tot_be += 1; trade_done = True; break
                                        elif hit_sl:
                                            tot_l += 1; tot_pips -= risk; curr_l += 1
                                            if curr_l > max_consec_l: max_consec_l = curr_l
                                            trade_done = True; break

                    # Bearish
                    elif (not h1_match) and (not h4_match) and p1['close'] < p1['open']:
                        if cur['high'] < p2['low'] - (1.5 * pip):
                            fvg_bottom = cur['high']
                            fvg_top = p2['low']
                            sl = fvg_top + (3.5 * pip)
                            risk = (sl - fvg_bottom) / pip
                            if 6.0 <= risk <= 20.0:
                                future = day_data[day_data['time'] > c_time].head(10).to_dict('records')
                                for f in future:
                                    if fvg_bottom <= f['high'] <= fvg_top:
                                        entry = fvg_bottom
                                        tp = entry - (risk * rr * pip)
                                        be_price = entry - (risk * be_trigger_mult * pip) if be_trigger_mult else None

                                        outcome = day_data[day_data['time'] > f['time']].head(30).to_dict('records')
                                        hit_tp, hit_sl, hit_be = False, False, False
                                        curr_sl = sl

                                        for o in outcome:
                                            if be_price and o['low'] <= be_price:
                                                curr_sl = entry - (0.5 * pip)
                                            if o['high'] >= curr_sl:
                                                if curr_sl < sl: hit_be = True
                                                else: hit_sl = True
                                                break
                                            if o['low'] <= tp:
                                                hit_tp = True
                                                break

                                        if hit_tp:
                                            tot_w += 1; tot_pips += risk * rr; curr_l = 0; trade_done = True; break
                                        elif hit_be:
                                            tot_be += 1; trade_done = True; break
                                        elif hit_sl:
                                            tot_l += 1; tot_pips -= risk; curr_l += 1
                                            if curr_l > max_consec_l: max_consec_l = curr_l
                                            trade_done = True; break

        t = tot_w + tot_be + tot_l
        decisive = tot_w + tot_l
        wr = (tot_w / decisive * 100) if decisive > 0 else 0
        usd_pnl = tot_pips * 10 * 0.50
        grid_results.append({
            "name": p["name"], "trades": t, "wins": tot_w, "be": tot_be, "losses": tot_l,
            "wr": wr, "max_cl": max_consec_l, "profit": usd_pnl
        })

    print(f"{'SETUP CONFIGURATION':<40} | {'TRADES':<6} | {'WINS':<4} | {'BE':<3} | {'LOSS':<4} | {'WIN RATE':<9} | {'MAX CONSEC L':<12} | {'PROFIT ($0.50)':<14}", flush=True)
    print("-" * 108, flush=True)
    for r in grid_results:
        print(f"{r['name']:<40} | {r['trades']:<6} | {r['wins']:<4} | {r['be']:<3} | {r['losses']:<4} | {r['wr']:6.1f}%   | {r['max_cl']:<12} | ${r['profit']:+10.2f}", flush=True)
    print("=" * 108, flush=True)

    mt5.shutdown()

if __name__ == "__main__":
    run_grid_search()
