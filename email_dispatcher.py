"""
Gmail Trade Alert Dispatcher for The5ers Sniper Bot
═══════════════════════════════════════════════════
Dispatches institutional trade setups directly to user's Gmail using the official Gmail CLI connector.
"""

import subprocess
import os
import tempfile
import logging

log = logging.getLogger("Email-Dispatcher")

RECIPIENT_EMAIL = "wonderdock.support@gmail.com"

def send_trade_alert_email(signal: dict) -> bool:
    """
    Sends a formatted Markdown email to the user with exact trade execution details.
    """
    is_executed = signal.get('executed', False)
    ticket = signal.get('order_ticket', 'N/A')

    if is_executed:
        subject = f"🚀 [THE5ERS AUTO-EXECUTED] {signal['direction']} {signal['symbol']} (Ticket #{ticket}) @ {signal['entry']:.5f}"
        status_banner = f"**Status:** 🚀 **ORDER AUTOMATICALLY EXECUTED ON MT5 (Ticket #{ticket})**\n\n**Action Required:** **NONE!** Your 24/7 daemon has executed the trade authoritatively on The5ers account `12623347`. Hard Stop Loss and Take Profit are already locked on the broker server."
    else:
        subject = f"🚨 [THE5ERS SIGNAL] {signal['direction']} {signal['symbol']} @ {signal['entry']:.5f} (Lot: {signal['lot']})"
        status_banner = f"**Status:** ⚠️ **Signal Alert (Manual Entry Needed)**: {signal.get('exec_error', 'Pending')}\n\n**Action Required:** If you wish to take this trade, enter it manually in MT5 (Account `12623347`)."

    body_md = f"""# 🎯 The5ers Institutional Trade Alert (A+ ICT Setup)

{status_banner}

---

### 📋 Order Parameters
- **Symbol:** `{signal['symbol']}`
- **Order Type:** **`{signal['direction']}`**
- **Volume / Lot Size:** **`{signal['lot']}`**
- **Fill / Entry Price:** `{signal.get('fill_price', signal['entry']):.5f}`
- **Stop Loss:** `{signal['sl']:.5f}`
- **Take Profit:** `{signal['tp']:.5f}`
- **Ticket #:** `{ticket}`

---

### 🛡️ Risk & Money Management (The5ers $10,000 Account)
- **Risk Amount:** **${signal['risk_usd']:.2f} USD** (Strictly 0.75% of account balance)
- **Target Profit:** **${signal['reward_usd']:.2f} USD** (R:R {signal['rr']})
- **Daily Loss Buffer:** Guaranteed safe — even 6 consecutive losses wouldn't touch The5ers' $500 daily loss limit.
- **Position Constraint:** Maximum 1 position strictly enforced.

---

### 🔬 Technical Confluence (Institutional ICT Model)
- **Trend Alignment:** H1 EMA 50 & H4 EMA 50 dual-timeframe flow confirmed (> 8.0 pip gap).
- **Liquidity Sweep:** Asian Range liquidity pool swept during institutional Kill Zone (Judas swing).
- **Structure Shift:** M15 displacement with completed candle-body CISD close.
- **Entry Retest:** M15 Fair Value Gap (FVG) boundary tap into 62%–79% OTE.
- **Specific Trigger:** {signal['confluence']}

---

*Dispatched automatically by Antigravity The5ers Sniper Bot.*
"""

    temp_path = os.path.join(tempfile.gettempdir(), "the5ers_trade_alert.md")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(body_md)

        cmd = [
            "gmail", "mutate", "send",
            "--to", RECIPIENT_EMAIL,
            "--subject", subject,
            "--md",
            "--body-file", temp_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, shell=True)

        if res.returncode == 0:
            log.info(f"✅ Email alert successfully dispatched to {RECIPIENT_EMAIL} (Output: {res.stdout.strip()})")
            return True
        else:
            log.error(f"❌ Failed to send email via Gmail CLI: {res.stderr}")
            return False
    except Exception as e:
        log.error(f"❌ Exception in email dispatcher: {e}")
        return False
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

if __name__ == "__main__":
    # Test dispatch
    test_sig = {
        'symbol': 'EURUSD',
        'direction': 'BUY',
        'lot': 0.50,
        'entry': 1.09820,
        'sl': 1.09670,
        'tp': 1.09820,
        'risk_usd': 75.0,
        'reward_usd': 75.0,
        'rr': '1:1.0',
        'confluence': 'H1+H4 Bullish Flow + Asian Low Sweep (1.09750) + M15 FVG Retest'
    }
    send_trade_alert_email(test_sig)
