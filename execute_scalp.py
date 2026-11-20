"""
Execute ICT Scalp Trade
"""

import sys
import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
from ict_engine import (
    detect_market_structure, detect_fvg, detect_order_blocks,
    detect_liquidity, get_pip_size, Bias, FVGType, OBType
)

def execute_scalp(symbol="AUDUSD"):
    if not mt5.initialize():
        print(f"MT5 Init Error: {mt5.last_error()}")
        return

    info = mt5.account_info()
    print(f"Connected: Login {info.login} on {info.server}")
    print(f"Algo Trading Enabled (trade_expert): {info.trade_expert}")

    pip_size = get_pip_size(symbol)
    rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
    df_m5 = pd.DataFrame(rates_m5)
    df_m5['time'] = pd.to_datetime(df_m5['time'], unit='s')
    df_m5 = df_m5.set_index('time')

    # Detect ICT zones on M5
    fvgs = detect_fvg(df_m5, min_size_pips=2.0, pip_size=pip_size, max_age=30)
    obs = detect_order_blocks(df_m5, lookback=20, min_body_ratio=0.5)

    tick = mt5.symbol_info_tick(symbol)
    sym_info = mt5.symbol_info(symbol)
    if not tick or not sym_info:
        print(f"Cannot get tick or symbol info for {symbol}")
        mt5.shutdown()
        return

    # Direction is SELL for AUDUSD
    entry_price = tick.bid
    digits = sym_info.digits

    # Stop Loss: Above the nearest Bearish OB / FVG high or recent swing high
    sl_candidates = [o.high for o in obs if o.type == OBType.BEARISH and not o.mitigated]
    sl_candidates += [f.high for f in fvgs if f.type == FVGType.BEARISH and not f.filled]

    if sl_candidates:
        sl = max(sl_candidates) + (3 * pip_size) # 3 pips buffer
    else:
        sl = entry_price + (15 * pip_size) # 15 pips safe default for M5 scalp

    risk_pips = (sl - entry_price) / pip_size
    if risk_pips < 8:
        sl = entry_price + (10 * pip_size)
        risk_pips = 10

    # TP at 1:2 Risk-Reward (Scalp target: 2x risk)
    tp = entry_price - (risk_pips * 2.0 * pip_size)

    entry_price = round(entry_price, digits)
    sl = round(sl, digits)
    tp = round(tp, digits)

    print("\n--- ICT SCALP TRADE PROPOSAL ---")
    print(f"Symbol:      {symbol}")
    print(f"Action:      SELL (Market Order)")
    print(f"Volume:      0.01 lot (Smallest test lot)")
    print(f"Entry Price: {entry_price}")
    print(f"Stop Loss:   {sl} (+{risk_pips:.1f} pips)")
    print(f"Take Profit: {tp} (-{risk_pips * 2.0:.1f} pips, 1:2 R:R)")

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": 0.01,
        "type": mt5.ORDER_TYPE_SELL,
        "price": entry_price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 777123,
        "comment": "ICT Scalp 0.01",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    print("\nSending order check...")
    check = mt5.order_check(request)
    print(f"Order Check Result: retcode={check.retcode}, comment={check.comment}, margin={check.margin}")

    print("\nAttempting order execution...")
    result = mt5.order_send(request)
    if result is None:
        print(f"Order Send Failed: {mt5.last_error()}")
    elif result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order Send Retcode: {result.retcode} - {result.comment}")
        if result.retcode == 10027 or "disabled" in result.comment.lower() or not info.trade_expert:
            print("\n>>> NOTICE: AutoTrading / Algo Trading is disabled in MT5 terminal.")
            print(">>> Please click the 'Algo Trading' button at the top toolbar in MetaTrader 5 to enable it!")
        elif "filling" in result.comment.lower():
            # Try FOK
            request["type_filling"] = mt5.ORDER_FILLING_FOK
            res2 = mt5.order_send(request)
            print(f"Retry with FOK: {res2.retcode} - {res2.comment}")
    else:
        print(f"\n SUCCESS! Order Executed!")
        print(f"Deal Ticket:  {result.deal}")
        print(f"Order Ticket: {result.order}")
        print(f"Price:        {result.price}")
        print(f"Volume:       {result.volume}")

    mt5.shutdown()

if __name__ == "__main__":
    execute_scalp()
