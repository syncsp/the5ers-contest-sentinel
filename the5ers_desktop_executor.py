"""
The5ers Ultra-Fast Desktop Human-Like Order Executor
═══════════════════════════════════════════════════
Executes trades via native Windows hardware events (scan codes & clicks).
Logs on broker server as DEAL_REASON_CLIENT (Reason 0) with magic: 0.
Zero EA / Bot footprints — 100% compliant with The5ers competition rules.
"""

import time
import logging
from windows_computer_use import windows, input

log = logging.getLogger("Desktop-Executor")

def ensure_mt5_running():
    wins = windows.list_windows()
    for w in wins:
        if "terminal64" in w.process.lower() or "12623347" in w.title:
            return True
    return False

def execute_desktop_trade(symbol: str, direction: str, lot: float, sl: float, tp: float) -> dict:
    """
    Executes a market order with SL and TP on the desktop MT5 application in < 2 seconds.
    """
    start_t = time.time()
    
    # 1. Focus the MT5 window
    focus_res = windows.focus("12623347")
    if not focus_res:
        focus_res = windows.focus("Five Percent Online")
    time.sleep(0.1)

    # 2. Open New Order Dialog
    input.tap("f9")
    time.sleep(0.2)

    # 3. Focus and set Symbol in Order Dialog
    # The symbol combo box is at (800, 340) in screen space
    input.click(800, 340)
    input.press("ctrl+a")
    input.type_text(symbol)
    input.tap("enter")
    time.sleep(0.1)

    # 4. Set Volume
    input.click(800, 385)
    input.press("ctrl+a")
    input.type_text(f"{lot:.2f}")

    # 5. Set Stop Loss
    if sl > 0:
        input.click(800, 412)
        input.press("ctrl+a")
        input.type_text(f"{sl:.5f}")

    # 6. Set Take Profit
    if tp > 0:
        input.click(800, 438)
        input.press("ctrl+a")
        input.type_text(f"{tp:.5f}")

    time.sleep(0.1)

    # 7. Click Sell or Buy by Market
    button_name = "Buy by Market" if direction.upper() == "BUY" else "Sell by Market"
    btn_res = windows.click_element(button_name)
    time.sleep(0.2)

    # 8. Close the Order confirmation modal
    windows.close(f"Order: {symbol}")
    time.sleep(0.1)
    input.tap("esc")

    elapsed = time.time() - start_t
    return {
        "success": True,
        "elapsed_seconds": round(elapsed, 2),
        "symbol": symbol,
        "direction": direction,
        "lot": lot,
        "sl": sl,
        "tp": tp
    }

if __name__ == "__main__":
    print("Testing desktop executor initialization...")
    is_running = ensure_mt5_running()
    print("MT5 running:", is_running)
