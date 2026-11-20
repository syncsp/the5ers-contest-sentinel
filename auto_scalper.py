"""
ICT Continuous Auto-Scalper for The5ers Contest
════════════════════════════════════════════════
Monitors market every 20s, identifies ICT setups, and executes 0.01 lot scalps.
"""

import time
import sys
import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone

from ict_engine import (
    detect_market_structure, detect_fvg, detect_order_blocks,
    detect_liquidity, score_setup, get_pip_size, Bias, FVGType, OBType
)

SYMBOLS = [
    'AUDUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD',
    'USDCAD', 'NZDUSD', 'CADJPY', 'GBPJPY', 'EURJPY'
]

MAX_OPEN_POSITIONS = 2
MIN_SCORE = 60
LOT_SIZE = 0.01

def check_open_positions():
    positions = mt5.positions_get()
    return len(positions) if positions else 0

def execute_trade(symbol, direction, entry_price, sl, tp, score, reason):
    sym_info = mt5.symbol_info(symbol)
    if not sym_info:
        return False

    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    digits = sym_info.digits

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": LOT_SIZE,
        "type": order_type,
        "price": round(entry_price, digits),
        "sl": round(sl, digits),
        "tp": round(tp, digits),
        "deviation": 20,
        "magic": 999888,
        "comment": f"ICT {score}%",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Order failed: {mt5.last_error()}")
        return False

    if result.retcode == 10027:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Algo Trading is disabled in MT5! Click 'Algo Trading' button in MT5.")
        return False
    elif result.retcode != mt5.TRADE_RETCODE_DONE:
        # Fallback to FOK filling
        request["type_filling"] = mt5.ORDER_FILLING_FOK
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Scalp Filled (FOK): {direction} {symbol} 0.01 @ {result.price} (SL: {sl}, TP: {tp})")
            return True
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Order error: {result.retcode} - {result.comment}")
        return False

    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Scalp Filled: {direction} {symbol} 0.01 @ {result.price} (SL: {sl}, TP: {tp})")
    return True

def run_scalper():
    if not mt5.initialize():
        print(f"MT5 Init Error: {mt5.last_error()}")
        return

    info = mt5.account_info()
    print("=" * 65)
    print("      ICT CONTEST CONTINUOUS AUTO-SCALPER ACTIVATED")
    print("=" * 65)
    print(f"Account:      {info.login} ({info.server})")
    print(f"Balance:      {info.balance} {info.currency}")
    print(f"Lot Size:     {LOT_SIZE} (conservative scalp)")
    print(f"Algo Trading: {'ENABLED ✅' if info.trade_expert else 'DISABLED ⚠️ (Enable in MT5 toolbar)'}")
    print("=" * 65)

    try:
        while True:
            # Refresh account info
            info = mt5.account_info()
            if not info:
                time.sleep(5)
                continue

            open_count = check_open_positions()
            if open_count >= MAX_OPEN_POSITIONS:
                time.sleep(15)
                continue

            best_setup = None
            best_score = 0

            for symbol in SYMBOLS:
                pip_size = get_pip_size(symbol)

                # HTF H1
                rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
                if rates_h1 is None or len(rates_h1) < 50:
                    continue
                df_h1 = pd.DataFrame(rates_h1)
                df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
                df_h1 = df_h1.set_index('time')
                htf = detect_market_structure(df_h1, lookback=50, swing_lb=4)
                if htf.bias == Bias.NEUTRAL:
                    continue

                # LTF M5
                rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
                if rates_m5 is None or len(rates_m5) < 50:
                    continue
                df_m5 = pd.DataFrame(rates_m5)
                df_m5['time'] = pd.to_datetime(df_m5['time'], unit='s')
                df_m5 = df_m5.set_index('time')
                ltf = detect_market_structure(df_m5, lookback=30, swing_lb=3)

                direction = "BUY" if htf.bias == Bias.BULLISH else "SELL"
                if ltf.bias != htf.bias:
                    continue  # Only trade with dual-timeframe ICT alignment

                fvgs = detect_fvg(df_m5, min_size_pips=1.5, pip_size=pip_size, max_age=30)
                obs = detect_order_blocks(df_m5, lookback=20, min_body_ratio=0.5)
                liq = detect_liquidity(df_m5, threshold_pips=2.0, pip_size=pip_size)

                score = score_setup(htf, fvgs, obs, liq, direction)
                if score >= MIN_SCORE and score > best_score:
                    tick = mt5.symbol_info_tick(symbol)
                    if not tick:
                        continue
                    entry = tick.ask if direction == "BUY" else tick.bid

                    # Calculate SL & TP
                    if direction == "BUY":
                        sl_cands = [o.low for o in obs if o.type == OBType.BULLISH and not o.mitigated]
                        sl_cands += [f.low for f in fvgs if f.type == FVGType.BULLISH and not f.filled]
                        sl = (min(sl_cands) - 3 * pip_size) if sl_cands else (entry - 12 * pip_size)
                        risk = max(entry - sl, 6 * pip_size)
                        sl = entry - risk
                        tp = entry + (risk * 2.0)
                    else:
                        sl_cands = [o.high for o in obs if o.type == OBType.BEARISH and not o.mitigated]
                        sl_cands += [f.high for f in fvgs if f.type == FVGType.BEARISH and not f.filled]
                        sl = (max(sl_cands) + 3 * pip_size) if sl_cands else (entry + 12 * pip_size)
                        risk = max(sl - entry, 6 * pip_size)
                        sl = entry + risk
                        tp = entry - (risk * 2.0)

                    best_setup = {
                        "symbol": symbol,
                        "direction": direction,
                        "entry": entry,
                        "sl": sl,
                        "tp": tp,
                        "score": score,
                        "reason": f"H1+M5 {direction} | Score: {score}%"
                    }
                    best_score = score

            if best_setup:
                now_str = datetime.now().strftime("%H:%M:%S")
                print(f"[{now_str}] 🎯 A+ Setup: {best_setup['direction']} {best_setup['symbol']} | Score: {best_setup['score']}%")
                execute_trade(
                    best_setup['symbol'],
                    best_setup['direction'],
                    best_setup['entry'],
                    best_setup['sl'],
                    best_setup['tp'],
                    best_setup['score'],
                    best_setup['reason']
                )

            time.sleep(20)

    except KeyboardInterrupt:
        print("\nStopping Scalper...")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    run_scalper()
