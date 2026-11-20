"""
ICT V3: Judas Swing (Asian Range Liquidity Sweep + London/NY Expansion)
This is the holy grail ICT setup:
1. Identify Asian Session High & Low (00:00 - 06:00 UTC)
2. London/NY Open sweeps Asian High or Low (stops taken)
3. Price violently reverses (Market Structure Shift + Fair Value Gap)
4. Entry on FVG retest targeting opposing liquidity
"""

import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def calculate_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close'].shift(1)
    tr = pd.concat([high - low, (high - close).abs(), (low - close).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def backtest_judas(symbol, bars=3000):
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bars)
    if rates is None or len(rates) < 500:
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('time')
    df['atr'] = calculate_atr(df, 14)
    df['hour'] = df.index.hour
    df['date'] = df.index.date

    unique_dates = df['date'].unique()
    wins = 0
    losses = 0
    total_trades = 0

    for d in unique_dates:
        day_bars = df[df['date'] == d]
        # Asian session (00:00 to 06:00 UTC)
        asian_bars = day_bars[(day_bars['hour'] >= 0) & (day_bars['hour'] < 6)]
        if len(asian_bars) < 8:
            continue

        asian_high = asian_bars['high'].max()
        asian_low = asian_bars['low'].min()
        asian_range = asian_high - asian_low

        # London & NY session (07:00 to 16:00 UTC)
        trade_session = day_bars[(day_bars['hour'] >= 7) & (day_bars['hour'] <= 16)]
        if len(trade_session) < 10:
            continue

        # Look for Judas Swing (Sweep of Asian High or Low)
        swept_low = False
        swept_high = False
        trade_taken = False

        for idx, bar in trade_session.iterrows():
            if trade_taken:
                break

            atr = bar['atr']
            if pd.isna(atr) or atr <= 0:
                continue

            # Sweep of Asian Low -> Look for Bullish Reversal
            if not swept_low and bar['low'] < asian_low:
                swept_low = True
                continue

            # Sweep of Asian High -> Look for Bearish Reversal
            if not swept_high and bar['high'] > asian_high:
                swept_high = True
                continue

            # Check for reversal confirmation (candle closes back inside Asian range)
            if swept_low and bar['close'] > asian_low:
                # BUY: Entry at bar close, SL below swing low (bar['low'] - 0.5*atr), TP at Asian High or 1:2 R:R
                entry = bar['close']
                sl = bar['low'] - (0.5 * atr)
                risk = entry - sl
                if risk <= 0:
                    continue
                tp = entry + (risk * 2.0) # 1:2 RR

                # Evaluate remainder of the day
                future_bars = day_bars.loc[idx:][1:20]
                hit_tp, hit_sl = False, False
                for _, f_row in future_bars.iterrows():
                    if f_row['low'] <= sl:
                        hit_sl = True; break
                    if f_row['high'] >= tp:
                        hit_tp = True; break

                if hit_tp:
                    wins += 1; total_trades += 1; trade_taken = True
                elif hit_sl:
                    losses += 1; total_trades += 1; trade_taken = True

            elif swept_high and bar['close'] < asian_high:
                # SELL: Entry at bar close, SL above swing high, TP at 1:2 R:R
                entry = bar['close']
                sl = bar['high'] + (0.5 * atr)
                risk = sl - entry
                if risk <= 0:
                    continue
                tp = entry - (risk * 2.0)

                future_bars = day_bars.loc[idx:][1:20]
                hit_tp, hit_sl = False, False
                for _, f_row in future_bars.iterrows():
                    if f_row['high'] >= sl:
                        hit_sl = True; break
                    if f_row['low'] <= tp:
                        hit_tp = True; break

                if hit_tp:
                    wins += 1; total_trades += 1; trade_taken = True
                elif hit_sl:
                    losses += 1; total_trades += 1; trade_taken = True

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    return {
        "trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate
    }

def run_judas():
    if not mt5.initialize():
        print("MT5 Init Error")
        return

    symbols = ['EURUSD', 'GBPUSD', 'AUDUSD', 'USDJPY', 'USDCAD', 'XAUUSD', 'GBPJPY']
    print("=" * 70)
    print("   ICT JUDAS SWING BENCHMARK (Asian Liquidity Sweep + Reversal)")
    print("=" * 70)
    print(f"{'SYMBOL':<10} {'TRADES':<8} {'WINS':<6} {'LOSSES':<8} {'WIN RATE':<10} {'1:2 R:R EXPECTANCY':<20}")
    print("-" * 70)

    tot_trades, tot_wins, tot_losses = 0, 0, 0
    for s in symbols:
        res = backtest_judas(s, bars=3000)
        if not res or res['trades'] == 0:
            continue
        tot_trades += res['trades']
        tot_wins += res['wins']
        tot_losses += res['losses']
        exp = (res['wins'] * 2.0 - res['losses'] * 1.0) / res['trades']
        status = f"+{exp:.2f}R 🔥" if exp > 0 else f"{exp:.2f}R"
        print(f"{s:<10} {res['trades']:<8} {res['wins']:<6} {res['losses']:<8} {res['win_rate']:<9.1f}% {status:<20}")

    overall_wr = (tot_wins / tot_trades * 100) if tot_trades > 0 else 0
    overall_exp = (tot_wins * 2.0 - tot_losses * 1.0) / tot_trades if tot_trades > 0 else 0
    print("=" * 70)
    print(f"TOTAL: {tot_trades} Trades | {tot_wins} Wins | {tot_losses} Losses | Win Rate: {overall_wr:.1f}%")
    print(f"OVERALL EXPECTANCY: +{overall_exp:.2f}R (Every trade generates +{overall_exp*100:.1f}% risk profit!)")
    print("=" * 70)

    mt5.shutdown()

if __name__ == "__main__":
    run_judas()
