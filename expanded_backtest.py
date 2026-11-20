"""
Expanded Backtest: Asian Range Sweep + NY/London Kill Zones (10,000 bars / ~1.5 Years)
═══════════════════════════════════════════════════════════════════════════════════════
Evaluates larger sample size across EURUSD, GBPUSD, USDJPY, USDCAD, AUDUSD, EURGBP, GBPJPY
"""

import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def run_expanded_test():
    if not mt5.initialize(): return

    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD', 'GBPJPY']
    for s in symbols: mt5.symbol_select(s, True)

    print("=" * 90)
    print("   EXPANDED 1.5-YEAR BACKTEST: LONDON & NY SESSIONS (1:1.2 & 1:1.5 RR)")
    print("=" * 90)

    for rr in [1.2, 1.5, 2.0]:
        tot_trades, tot_wins, tot_losses = 0, 0, 0
        tot_pnl_pips = 0.0
        pair_breakdown = {}

        for s in symbols:
            pip = 0.01 if "JPY" in s else 0.0001
            bars_m15 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_M15, 0, 10000)
            bars_d1 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_D1, 0, 250)
            if bars_m15 is None or bars_d1 is None or len(bars_m15) < 1000: continue

            df_m15 = pd.DataFrame(bars_m15)
            df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
            df_m15 = df_m15.set_index('time')
            df_m15['hour'] = df_m15.index.hour
            df_m15['date'] = df_m15.index.date

            df_d1 = pd.DataFrame(bars_d1)
            df_d1['time'] = pd.to_datetime(df_d1['time'], unit='s')
            df_d1 = df_d1.set_index('time')
            df_d1['ema20'] = df_d1['close'].ewm(span=20, adjust=False).mean()
            df_d1['date'] = df_d1.index.date
            d1_bias = dict(zip(df_d1['date'], df_d1['close'] > df_d1['ema20']))

            dates = df_m15['date'].unique()
            p_wins, p_losses = 0, 0

            for d in dates:
                if d not in d1_bias: continue
                d1_bull = d1_bias[d]
                day = df_m15[df_m15['date'] == d]
                if len(day) < 20: continue

                # Asian Range 00:00 - 06:00
                asian = day[(day['hour'] >= 0) & (day['hour'] < 6)]
                if len(asian) < 4: continue
                a_high = asian['high'].max()
                a_low = asian['low'].min()
                if not (10.0 <= (a_high - a_low) / pip <= 45.0): continue

                # Kill Zones: London (07:00 - 10:00) & NY Open (12:00 - 15:00)
                kz = day[((day['hour'] >= 7) & (day['hour'] <= 10)) | ((day['hour'] >= 12) & (day['hour'] <= 15))]
                if len(kz) < 4: continue

                trade_done = False
                for idx, bar in kz.iterrows():
                    if trade_done: break

                    # BUY Setup: Asian Low swept + candle closes back above Asian Low (Liquidity Grab / Turtle Soup)
                    if d1_bull and bar['low'] < a_low and bar['close'] > a_low:
                        entry = bar['close']
                        sl = bar['low'] - (3.0 * pip)
                        risk = (entry - sl) / pip
                        if 8.0 <= risk <= 25.0:
                            tp = entry + (risk * rr * pip)
                            future = day.loc[idx:][1:30]
                            hit_tp, hit_sl = False, False
                            for _, f in future.iterrows():
                                if f['low'] <= sl: hit_sl = True; break
                                if f['high'] >= tp: hit_tp = True; break

                            if hit_tp:
                                p_wins += 1; tot_wins += 1; tot_pnl_pips += risk * rr; trade_done = True
                            elif hit_sl:
                                p_losses += 1; tot_losses += 1; tot_pnl_pips -= risk; trade_done = True

                    # SELL Setup: Asian High swept + candle closes back below Asian High
                    elif not d1_bull and bar['high'] > a_high and bar['close'] < a_high:
                        entry = bar['close']
                        sl = bar['high'] + (3.0 * pip)
                        risk = (sl - entry) / pip
                        if 8.0 <= risk <= 25.0:
                            tp = entry - (risk * rr * pip)
                            future = day.loc[idx:][1:30]
                            hit_tp, hit_sl = False, False
                            for _, f in future.iterrows():
                                if f['high'] >= sl: hit_sl = True; break
                                if f['low'] <= tp: hit_tp = True; break

                            if hit_tp:
                                p_wins += 1; tot_wins += 1; tot_pnl_pips += risk * rr; trade_done = True
                            elif hit_sl:
                                p_losses += 1; tot_losses += 1; tot_pnl_pips -= risk; trade_done = True

            pair_breakdown[s] = (p_wins, p_losses)

        tot_trades = tot_wins + tot_losses
        wr = (tot_wins / tot_trades * 100) if tot_trades > 0 else 0
        profit_usd = tot_pnl_pips * 10 * 0.50
        print(f"R:R 1:{rr:.1f} ── Total Trades: {tot_trades:<4} │ Wins: {tot_wins:<3} │ Losses: {tot_losses:<3} │ Win Rate: {wr:5.1f}% │ Net Pips: {tot_pnl_pips:+8.1f}p │ Profit ($0.50 Lot): ${profit_usd:+9.2f} USD")
        for sym, (pw, pl) in pair_breakdown.items():
            ptot = pw + pl
            pwr = (pw / ptot * 100) if ptot > 0 else 0
            print(f"   {sym:<8}: {ptot:<3} trades | {pw:<2} wins | {pl:<2} losses | WR: {pwr:5.1f}%")
        print("-" * 90)

    print("=" * 90)
    mt5.shutdown()

if __name__ == "__main__":
    run_expanded_test()
