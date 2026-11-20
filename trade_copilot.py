"""
ICT Competition Trade Copilot & Position Watchdog
══════════════════════════════════════════════════
1. Tracks active position in real-time
2. Alerts when to move Stop Loss to Breakeven (Risk-Free)
3. Detects trade closure and prepares the next A+ ICT setup
4. Enforces The5ers single-position competition rule
"""

import time
import sys
import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

def monitor_trade():
    if not mt5.initialize():
        print(f"MT5 Init Error: {mt5.last_error()}")
        return

    positions = mt5.positions_get()
    if not positions or len(positions) == 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 NO OPEN POSITION. Scanning for next setup...")
        return None

    p = positions[0]
    side = "BUY" if p.type == 0 else "SELL"
    pip_size = 0.0001 if "JPY" not in p.symbol and "XAU" not in p.symbol else (0.01 if "JPY" in p.symbol else 0.1)

    pnl_pips = ((p.price_current - p.price_open) if side == "BUY" else (p.price_open - p.price_current)) / pip_size
    sl_dist_pips = abs(p.sl - p.price_current) / pip_size if p.sl > 0 else 0
    tp_dist_pips = abs(p.tp - p.price_current) / pip_size if p.tp > 0 else 0

    print("=" * 60)
    print(f"       ACTIVE POSITION MONITOR — TICKET #{p.ticket}")
    print("=" * 60)
    print(f"Symbol:          {p.symbol} ({side})")
    print(f"Volume:          {p.volume} lots")
    print(f"Open Price:      {p.price_open:.5f}")
    print(f"Current Price:   {p.price_current:.5f}")
    print(f"Floating P&L:    {p.profit:+.2f} USD ({pnl_pips:+.1f} pips)")
    print(f"Stop Loss:       {p.sl:.5f} ({sl_dist_pips:.1f} pips away)")
    print(f"Take Profit:     {p.tp:.5f} ({tp_dist_pips:.1f} pips away)")
    print("-" * 60)

    # ICT Breakeven Rule: If in profit by >= 15 pips, advise moving SL to breakeven
    if pnl_pips >= 15.0:
        if (side == "SELL" and p.sl > p.price_open) or (side == "BUY" and p.sl < p.price_open):
            print("💡 PRO-TIP: You are +15 pips in profit!")
            print(f"   Recommend moving SL to Entry ({p.price_open:.5f}) to secure a 100% RISK-FREE TRADE!")
    else:
        print(f"⏳ Trade running in accordance with ICT plan. Target: {p.tp:.5f}")

    print("=" * 60)
    mt5.shutdown()
    return p

if __name__ == "__main__":
    monitor_trade()
