"""
FVG Retest Deep Optimization: Maximizing Win Rate & Profit Expectancy
════════════════════════════════════════════════════════════════════
Tests:
- R:R ratios from 1:1.0 up to 1:2.0
- Timeframe confirmation: M15 FVG with H1 Trend Alignment
- Kill Zone timing: London Open (07:00-11:00 UTC) vs NY Open (12:00-16:00 UTC)
- Major pairs: EURUSD, GBPUSD, USDJPY, USDCAD, AUDUSD
"""

import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def run_fvg_optimization():
    if not mt5.initialize(): return

    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD']
    for s in symbols: mt5.symbol_select(s, True)

    print("=" * 88)
    print("      DEEP DIVE: M15 FVG RETEST OPTIMIZATION ACROSS KILL ZONES")
    print("=" * 88)

    results_by_rr = {}

    for rr in [1.0, 1.2, 1.5, 1.8, 2.0]:
        tot_trades, tot_wins, tot_losses = 0, 0, 0
        tot_pnl_pips = 0.0
        pair_stats = {}

        for s in symbols:
            pip = 0.01 if "JPY" in s else 0.0001
            bars_m15 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_M15, 0, 6000)
            bars_h1 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_H1, 0, 2000)
            if bars_m15 is None or bars_h1 is None: continue

            df_m15 = pd.DataFrame(bars_m15)
            df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
            df_m15 = df_m15.set_index('time')
            df_m15['hour'] = df_m15.index.hour
            df_m15['date'] = df_m15.index.date

            df_h1 = pd.DataFrame(bars_h1)
            df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
            df_h1 = df_h1.set_index('time')
            df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()
            h1_bias = df_h1['close'] > df_h1['ema50']

            dates = df_m15['date'].unique()
            pw, pl = 0, 0

            for d in dates:
                day_m15 = df_m15[df_m15['date'] == d]
                if len(day_m15) < 20: continue

                # Look for trades in London (07:00-11:00) and NY (12:00-16:00)
                session = day_m15[((day_m15['hour'] >= 7) & (day_m15['hour'] <= 11)) | ((day_m15['hour'] >= 12) & (day_m15['hour'] <= 16))]
                if len(session) < 8: continue

                trade_taken = False
                bars_list = list(session.iterrows())
                for i in range(2, len(bars_list)):
                    if trade_taken: break
                    c_time, cur = bars_list[i]
                    p2_time, bar_p2 = bars_list[i-2]
                    p1_time, bar_p1 = bars_list[i-1]

                    # Get H1 trend at this exact timestamp
                    h1_match = h1_bias.asof(c_time)
                    if pd.isna(h1_match): continue

                    # Bullish FVG: Bar 1 strong green, current low > bar 3 high
                    if h1_match and bar_p1['close'] > bar_p1['open']:
                        if cur['low'] > bar_p2['high'] + (1.5 * pip):
                            fvg_top = cur['low']
                            fvg_bottom = bar_p2['high']
                            fvg_size = (fvg_top - fvg_bottom) / pip

                            if 2.0 <= fvg_size <= 15.0:
                                # Look for retest in the next 12 bars (3 hours)
                                future = day_m15.loc[c_time:][1:12]
                                for ret_idx, f in future.iterrows():
                                    if fvg_bottom <= f['low'] <= fvg_top:
                                        # Entry on touch of FVG
                                        entry = fvg_top
                                        sl = fvg_bottom - (3.0 * pip)
                                        risk = (entry - sl) / pip
                                        if 6.0 <= risk <= 20.0:
                                            tp = entry + (risk * rr * pip)

                                            # Outcome
                                            outcome = day_m15.loc[ret_idx:][1:25]
                                            hit_tp, hit_sl = False, False
                                            for _, o in outcome.iterrows():
                                                if o['low'] <= sl: hit_sl = True; break
                                                if o['high'] >= tp: hit_tp = True; break

                                            if hit_tp:
                                                pw += 1; tot_wins += 1; tot_pnl_pips += risk * rr; trade_taken = True; break
                                            elif hit_sl:
                                                pl += 1; tot_losses += 1; tot_pnl_pips -= risk; trade_taken = True; break

                    # Bearish FVG: Bar 1 strong red, current high < bar 3 low
                    elif (not h1_match) and bar_p1['close'] < bar_p1['open']:
                        if cur['high'] < bar_p2['low'] - (1.5 * pip):
                            fvg_bottom = cur['high']
                            fvg_top = bar_p2['low']
                            fvg_size = (fvg_top - fvg_bottom) / pip

                            if 2.0 <= fvg_size <= 15.0:
                                future = day_m15.loc[c_time:][1:12]
                                for ret_idx, f in future.iterrows():
                                    if fvg_bottom <= f['high'] <= fvg_top:
                                        entry = fvg_bottom
                                        sl = fvg_top + (3.0 * pip)
                                        risk = (sl - entry) / pip
                                        if 6.0 <= risk <= 20.0:
                                            tp = entry - (risk * rr * pip)

                                            outcome = day_m15.loc[ret_idx:][1:25]
                                            hit_tp, hit_sl = False, False
                                            for _, o in outcome.iterrows():
                                                if o['high'] >= sl: hit_sl = True; break
                                                if o['low'] <= tp: hit_tp = True; break

                                            if hit_tp:
                                                pw += 1; tot_wins += 1; tot_pnl_pips += risk * rr; trade_taken = True; break
                                            elif hit_sl:
                                                pl += 1; tot_losses += 1; tot_pnl_pips -= risk; trade_taken = True; break

            pair_stats[s] = (pw, pl)

        tot_trades = tot_wins + tot_losses
        wr = (tot_wins / tot_trades * 100) if tot_trades > 0 else 0
        profit_usd = tot_pnl_pips * 10 * 0.50
        print(f"R:R 1:{rr:.1f} ── Trades: {tot_trades:<4} │ Wins: {tot_wins:<3} │ Losses: {tot_losses:<3} │ Win Rate: {wr:5.1f}% │ Net Pips: {tot_pnl_pips:+8.1f}p │ Profit ($0.50 Lot): ${profit_usd:+9.2f} USD")
        for sym, (pw, pl) in pair_stats.items():
            ptot = pw + pl
            pwr = (pw / ptot * 100) if ptot > 0 else 0
            print(f"   {sym:<8}: {ptot:<3} trades | {pw:<2} wins | {pl:<2} losses | WR: {pwr:5.1f}%")
        print("-" * 88)

    print("=" * 88)
    mt5.shutdown()

if __name__ == "__main__":
    run_fvg_optimization()
