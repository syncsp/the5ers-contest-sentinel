import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime

def full_gold_deepdive():
    if not mt5.initialize():
        print("Failed to initialize MT5")
        return

    symbol = "XAUUSD"
    tick = mt5.symbol_info_tick(symbol)
    s_info = mt5.symbol_info(symbol)
    
    print("=" * 60)
    print("   INSTITUTIONAL XAUUSD DEEP-DIVE AUDIT")
    print(f"   Time (Server): {datetime.fromtimestamp(tick.time)}")
    print(f"   Live Bid: {tick.bid:.2f} | Ask: {tick.ask:.2f} | Spread: {(tick.ask - tick.bid):.2f}")
    print("=" * 60)

    # 1. Higher Timeframe Direction (H4 & H1)
    rates_h4 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 50))
    rates_h4['datetime'] = pd.to_datetime(rates_h4['time'], unit='s')
    
    rates_h1 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 50))
    rates_h1['datetime'] = pd.to_datetime(rates_h1['time'], unit='s')

    # H4 Trend & Momentum
    h4_last = rates_h4.iloc[-1]
    h4_prev = rates_h4.iloc[-2]
    h4_2prev = rates_h4.iloc[-3]
    print("\n[1] H4 MARKET STRUCTURE:")
    print(f"  H4 Current Bar ({h4_last['datetime']}): O={h4_last['open']:.2f}, H={h4_last['high']:.2f}, L={h4_last['low']:.2f}, C={h4_last['close']:.2f}")
    print(f"  H4 Previous Bar ({h4_prev['datetime']}): O={h4_prev['open']:.2f}, H={h4_prev['high']:.2f}, L={h4_prev['low']:.2f}, C={h4_prev['close']:.2f}")
    h4_trend = "STRONG BEARISH DISPLACEMENT" if h4_last['close'] < h4_prev['low'] or h4_last['close'] < h4_last['open'] else "BULLISH EXPANSION"
    print(f"  H4 Flow Bias: {h4_trend}")

    # H1 Trend & Momentum
    print("\n[2] H1 MARKET STRUCTURE:")
    for _, r in rates_h1.tail(6).iterrows():
        delta = r['close'] - r['open']
        bias = "BEARISH ▼" if delta < 0 else "BULLISH ▲"
        print(f"  H1 {r['datetime']} | O:{r['open']:.2f} H:{r['high']:.2f} L:{r['low']:.2f} C:{r['close']:.2f} | {bias} (${delta:+.2f})")

    # 2. Key Daily & Session Reference Points
    rates_d1 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 5))
    rates_d1['datetime'] = pd.to_datetime(rates_d1['time'], unit='s')
    d_curr = rates_d1.iloc[-1]
    
    rates_m15 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100))
    rates_m15['datetime'] = pd.to_datetime(rates_m15['time'], unit='s')
    today_date = d_curr['datetime'].date()
    m15_today = rates_m15[rates_m15['datetime'].dt.date == today_date]

    asian_bars = m15_today[(m15_today['datetime'].dt.hour >= 0) & (m15_today['datetime'].dt.hour < 8)]
    asian_h = asian_bars['high'].max() if not asian_bars.empty else None
    asian_l = asian_bars['low'].min() if not asian_bars.empty else None

    london_bars = m15_today[(m15_today['datetime'].dt.hour >= 8) & (m15_today['datetime'].dt.hour < 14)]
    london_h = london_bars['high'].max() if not london_bars.empty else None
    london_l = london_bars['low'].min() if not london_bars.empty else None

    ny_am_bars = m15_today[(m15_today['datetime'].dt.hour >= 14) & (m15_today['datetime'].dt.hour < 18)]
    ny_am_h = ny_am_bars['high'].max() if not ny_am_bars.empty else None
    ny_am_l = ny_am_bars['low'].min() if not ny_am_bars.empty else None

    ny_pm_bars = m15_today[m15_today['datetime'].dt.hour >= 18]
    ny_pm_h = ny_pm_bars['high'].max() if not ny_pm_bars.empty else None
    ny_pm_l = ny_pm_bars['low'].min() if not ny_pm_bars.empty else None

    print("\n[3] INSTITUTIONAL REFERENCE FRAMEWORK:")
    print(f"  • Today's High (Daily Extremum): ${d_curr['high']:.2f}")
    print(f"  • Today's Low (Daily Extremum):  ${d_curr['low']:.2f}")
    print(f"  • Daily Open:                   ${d_curr['open']:.2f}")
    print(f"  • Asian Session Range:          ${asian_l:.2f} - ${asian_h:.2f} (Range: ${asian_h - asian_l:.2f})")
    print(f"  • London Session Range:         ${london_l:.2f} - ${london_h:.2f} (Range: ${london_h - london_l:.2f})")
    print(f"  • NY Morning Session Range:     ${ny_am_l:.2f} - ${ny_am_h:.2f} (Range: ${ny_am_h - ny_am_l:.2f})")
    print(f"  • NY PM Afternoon Range:        ${ny_pm_l:.2f} - ${ny_pm_h:.2f} (Range: ${ny_pm_h - ny_pm_l:.2f})")

    # 3. Liquidity Targets & Order Flow
    print("\n[4] LIQUIDITY MATRIX & TARGETS:")
    cp = tick.bid
    print(f"  Current Live Price: ${cp:.2f}")
    print(f"  ▼ SELL-SIDE LIQUIDITY (SSL):")
    print(f"    - NY PM Session Low:     ${ny_pm_l:.2f} (Distance: -${cp - ny_pm_l:.2f})")
    print(f"    - Asian Session Low:     ${asian_l:.2f} (Distance: -${cp - asian_l:.2f}) -> MAJOR MACRO POOL")
    print(f"    - Psychological $3520:   $3520.00 (Distance: -${cp - 3520:.2f})")
    print(f"    - Psychological $3515:   $3515.00 (Distance: -${cp - 3515:.2f})")
    print(f"    - Psychological $3510:   $3510.00 (Distance: -${cp - 3510:.2f})")
    print(f"    - Major Level $3500:     $3500.00 (Distance: -${cp - 3500:.2f})")
    print(f"  ▲ BUY-SIDE LIQUIDITY (BSL):")
    print(f"    - Recent M5 Swing High:  $3533.50 (Distance: +${3533.50 - cp:.2f})")
    print(f"    - NY PM Session High:    ${ny_pm_h:.2f} (Distance: +${ny_pm_h - cp:.2f})")
    print(f"    - NY AM Session High:    ${ny_am_h:.2f} (Distance: +${ny_am_h - cp:.2f})")

    # 4. Premium / Discount Equilibrium Analysis
    # Dealing Range for the NY Afternoon drop: from NY AM High $3586.07 down to current Low $3520.36
    high_leg = 3586.07
    low_leg = 3520.36
    eq_leg = (high_leg + low_leg) / 2.0
    print("\n[5] DEALING RANGE & EQUILIBRIUM (NY PM Expansion Leg):")
    print(f"  Dealing Range: ${low_leg:.2f} - ${high_leg:.2f} (Range: ${high_leg - low_leg:.2f})")
    print(f"  Equilibrium (50%): ${eq_leg:.2f}")
    print(f"  Discount Zone: < ${eq_leg:.2f} (Current Price ${cp:.2f} is in DEEP DISCOUNT of this leg)")
    print(f"  Optimal Trade Entry (OTE 62%-79% retracement of the leg): ${low_leg + 0.618*(high_leg - low_leg):.2f} - ${low_leg + 0.786*(high_leg - low_leg):.2f}")

    # Shorter Term Dealing Range (from 18:55 High $3547.29 down to 19:48 Low $3520.36):
    micro_high = 3547.29
    micro_low = 3520.36
    micro_eq = (micro_high + micro_low) / 2.0
    ote_62 = micro_low + 0.618 * (micro_high - micro_low)
    ote_70 = micro_low + 0.705 * (micro_high - micro_low)
    ote_79 = micro_low + 0.786 * (micro_high - micro_low)
    print(f"\n  Micro Dealing Range (18:55 High -> 19:48 Low):")
    print(f"    Range: ${micro_low:.2f} - ${micro_high:.2f} (${micro_high - micro_low:.2f})")
    print(f"    Equilibrium (50%): ${micro_eq:.2f}")
    print(f"    OTE 61.8%: ${ote_62:.2f}")
    print(f"    OTE 70.5%: ${ote_70:.2f}")
    print(f"    OTE 78.6%: ${ote_79:.2f}")

    # 5. Position Sizing Matrix (Fixed $75.00 Risk)
    print("\n[6] PRECISION COMMODITY POSITION SIZING MATRIX (Fixed $75.00 USD Risk):")
    print("  Note: 1 Standard Lot = 100 oz. $1.00 Price Movement = $100.00 / lot.")
    print("  SL Dist ($) | SL Points | Lot Size | Actual Risk ($) | Pips/Points Risk")
    for sl_dist in [1.50, 2.00, 2.50, 3.00, 3.50, 4.00, 5.00]:
        exact_lot = 75.0 / (sl_dist * 100.0)
        broker_lot = round(exact_lot, 2)
        actual_risk = broker_lot * sl_dist * 100.0
        print(f"    ${sl_dist:.2f}       | {int(sl_dist*10):3d} pts  | {broker_lot:.2f} lot  | ${actual_risk:6.2f} USD    | {sl_dist*10:.0f} pips")

    mt5.shutdown()

if __name__ == "__main__":
    full_gold_deepdive()
