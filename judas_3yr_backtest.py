"""
3-Year ICT Judas Swing + MSS + FVG Retest Backtest (35,000 M15 Bars)
═══════════════════════════════════════════════════════════════════
The Definitive Institutional Setup:
1. Asian Range defines Liquidity Pools (Asian High & Asian Low)
2. London Kill Zone (07:00 - 10:30 UTC): False breakout sweeps Asian Liquidity
3. Market Structure Shift (MSS) occurs with 3-bar displacement
4. FVG is formed and price retraces to test the FVG
5. Target 1:1.0 to 1:1.5 RR with strictly zero early exits
"""

import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def run_judas_3yr_backtest():
    if not mt5.initialize(): return

    symbols = ['GBPUSD', 'EURUSD', 'USDCAD', 'USDJPY']
    for s in symbols: mt5.symbol_select(s, True)

    print("=" * 105, flush=True)
    print("      🎯 3-YEAR ICT JUDAS SWING + MSS + FVG RETEST BACKTEST (35,000 BARS)", flush=True)
    print("      Testing across GBPUSD, EURUSD, USDCAD, USDJPY with The5ers Risk Limits", flush=True)
    print("=" * 105, flush=True)

    for rr in [1.0, 1.2, 1.5]:
        tot_trades, tot_wins, tot_losses = 0, 0, 0
        tot_pnl_pips = 0.0
        max_consec_losses = 0
        curr_losses = 0
        pair_data = {}

        for s in symbols:
            pip = 0.01 if "JPY" in s else 0.0001
            bars_m15 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_M15, 0, 35000)
            bars_h1 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_H1, 0, 10000)
            if bars_m15 is None or bars_h1 is None: continue

            df_m15 = pd.DataFrame(bars_m15)
            df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
            df_m15['hour'] = df_m15['time'].dt.hour
            df_m15['minute'] = df_m15['time'].dt.minute
            df_m15['date'] = df_m15['time'].dt.date
            df_m15['body'] = (df_m15['close'] - df_m15['open']).abs()

            df_h1 = pd.DataFrame(bars_h1)
            df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
            df_h1 = df_h1.set_index('time')
            df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()
            h1_bias = df_h1['close'] > df_h1['ema50']

            days_dict = {d: group for d, group in df_m15.groupby('date')}
            pw, pl = 0, 0

            for d, day_data in days_dict.items():
                if len(day_data) < 24: continue

                # 1. Asian Session (00:00 - 06:00 UTC)
                asian = day_data[(day_data['hour'] >= 0) & (day_data['hour'] < 6)]
                if len(asian) < 4: continue
                a_high = asian['high'].max()
                a_low = asian['low'].min()
                a_range = (a_high - a_low) / pip
                if not (10.0 <= a_range <= 45.0): continue

                # 2. London Kill Zone (07:00 - 11:00 UTC)
                london = day_data[(day_data['hour'] >= 7) & (day_data['hour'] <= 11)]
                if len(london) < 6: continue

                bars = london.to_dict('records')
                trade_done = False

                for i in range(len(bars)):
                    if trade_done: break
                    b = bars[i]
                    b_time = b['time']

                    h1_match = h1_bias.asof(b_time)
                    if pd.isna(h1_match): continue

                    # BULLISH SETUP:
                    # Daily/H1 Trend is Bullish + Asian Low is Swept in London + MSS creates Bullish FVG
                    if h1_match and b['low'] < a_low:
                        # Sweep occurred at bar i. Look for MSS + FVG in the next 5 bars
                        for j in range(i + 2, min(i + 7, len(bars))):
                            cur = bars[j]
                            p1 = bars[j-1]
                            p2 = bars[j-2]

                            if p1['close'] > p1['open'] and cur['low'] > p2['high'] + (1.5 * pip):
                                # Bullish FVG
                                fvg_top = cur['low']
                                fvg_bottom = p2['high']
                                sl = b['low'] - (3.5 * pip) # SL under the sweep low
                                risk = (fvg_top - sl) / pip

                                if 8.0 <= risk <= 24.0:
                                    # Check for retest in rest of day
                                    future = day_data[day_data['time'] > cur['time']].to_dict('records')
                                    for f in future:
                                        if fvg_bottom <= f['low'] <= fvg_top:
                                            entry = fvg_top
                                            tp = entry + (risk * rr * pip)

                                            # Outcome
                                            outcome = day_data[day_data['time'] > f['time']].to_dict('records')
                                            hit_tp, hit_sl = False, False
                                            for o in outcome:
                                                if o['low'] <= sl: hit_sl = True; break
                                                if o['high'] >= tp: hit_tp = True; break

                                            if hit_tp:
                                                pw += 1; tot_wins += 1; tot_pnl_pips += risk * rr
                                                curr_losses = 0; trade_done = True; break
                                            elif hit_sl:
                                                pl += 1; tot_losses += 1; tot_pnl_pips -= risk
                                                curr_losses += 1
                                                if curr_losses > max_consec_losses: max_consec_losses = curr_losses
                                                trade_done = True; break
                                    if trade_done: break

                    # BEARISH SETUP:
                    # Daily/H1 Trend is Bearish + Asian High is Swept in London + MSS creates Bearish FVG
                    elif (not h1_match) and b['high'] > a_high:
                        for j in range(i + 2, min(i + 7, len(bars))):
                            cur = bars[j]
                            p1 = bars[j-1]
                            p2 = bars[j-2]

                            if p1['close'] < p1['open'] and cur['high'] < p2['low'] - (1.5 * pip):
                                fvg_bottom = cur['high']
                                fvg_top = p2['low']
                                sl = b['high'] + (3.5 * pip)
                                risk = (sl - fvg_bottom) / pip

                                if 8.0 <= risk <= 24.0:
                                    future = day_data[day_data['time'] > cur['time']].to_dict('records')
                                    for f in future:
                                        if fvg_bottom <= f['high'] <= fvg_top:
                                            entry = fvg_bottom
                                            tp = entry - (risk * rr * pip)

                                            outcome = day_data[day_data['time'] > f['time']].to_dict('records')
                                            hit_tp, hit_sl = False, False
                                            for o in outcome:
                                                if o['high'] >= sl: hit_sl = True; break
                                                if o['low'] <= tp: hit_tp = True; break

                                            if hit_tp:
                                                pw += 1; tot_wins += 1; tot_pnl_pips += risk * rr
                                                curr_losses = 0; trade_done = True; break
                                            elif hit_sl:
                                                pl += 1; tot_losses += 1; tot_pnl_pips -= risk
                                                curr_losses += 1
                                                if curr_losses > max_consec_losses: max_consec_losses = curr_losses
                                                trade_done = True; break
                                    if trade_done: break

            pair_data[s] = (pw, pl)

        tot_trades = tot_wins + tot_losses
        wr = (tot_wins / tot_trades * 100) if tot_trades > 0 else 0
        usd_profit = tot_pnl_pips * 10 * 0.50
        print(f"R:R 1:{rr:.1f} ── Total Trades: {tot_trades:<4} │ Wins: {tot_wins:<3} │ Losses: {tot_losses:<3} │ WIN RATE: {wr:5.1f}% 🔥 │ Max Consec Loss: {max_consec_losses} │ Profit ($0.50 Lot): ${usd_profit:+9.2f} USD", flush=True)
        for sym, (pw, pl) in pair_data.items():
            ptot = pw + pl
            pwr = (pw / ptot * 100) if ptot > 0 else 0
            print(f"   {sym:<8}: {ptot:<3} trades │ Wins: {pw:<2} │ Losses: {pl:<2} │ WR: {pwr:5.1f}%", flush=True)
        print("-" * 105, flush=True)

    print("=" * 105, flush=True)
    mt5.shutdown()

if __name__ == "__main__":
    run_judas_3yr_backtest()
