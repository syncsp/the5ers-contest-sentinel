"""
WhatsApp Trade Alert Dispatcher for The5ers & FTMO
══════════════════════════════════════════════════
Sends instant WhatsApp trade alerts directly to your phone using the free CallMeBot gateway.

Setup (Takes 30 seconds):
1. Add CallMeBot to WhatsApp: +34 644 41 87 20 (or click https://wa.me/34644418720?text=I%20allow%20callmebot%20to%20send%20me%20messages)
2. Send message: "I allow callmebot to send me messages"
3. CallMeBot will reply with your API key.
4. Put your phone number (with country code) and API key below or in config.py!
"""

import urllib.request
import urllib.parse
import logging

log = logging.getLogger("WhatsApp-Dispatcher")

# Indian Phone Number configured
PHONE_NUMBER = "+918795938920"
API_KEY = "YOUR_API_KEY"       # <-- Replace with the API key CallMeBot sends you

def send_whatsapp_alert(signal: dict, phone: str = PHONE_NUMBER, apikey: str = API_KEY) -> bool:
    """
    Sends a formatted instant trade alert to your personal WhatsApp.
    """
    if apikey == "YOUR_API_KEY":
        log.warning("WhatsApp API key not set. Alert sent to Gmail instead.")
        return False

    message = (
        f"🚨 *THE5ERS TRADE ALERT* 🚨\n\n"
        f"• *Pair:* {signal['symbol']}\n"
        f"• *Action:* {signal['direction']}\n"
        f"• *Lot Size:* {signal['lot']}\n"
        f"• *Entry:* {signal['entry']:.5f}\n"
        f"• *Stop Loss:* {signal['sl']:.5f}\n"
        f"• *Take Profit:* {signal['tp']:.5f}\n"
        f"• *Risk:* ${signal['risk_usd']:.2f} USD\n"
        f"• *Target:* ${signal['reward_usd']:.2f} USD (R:R {signal['rr']})\n\n"
        f"⚡ *Confluence:* {signal['confluence']}\n"
        f"🔒 Enter in MT5 (12623347) and let run."
    )

    encoded_text = urllib.parse.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded_text}&apikey={apikey}"

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                log.info(f"✅ WhatsApp trade alert successfully sent to {phone}!")
                return True
            else:
                log.error(f"❌ Failed to send WhatsApp message. Status: {response.status}")
                return False
    except Exception as e:
        log.error(f"❌ Exception in WhatsApp dispatcher: {e}")
        return False

if __name__ == "__main__":
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
        'confluence': 'H1+H4 Bullish Flow + Asian Low Sweep + M15 FVG Retest'
    }
    send_whatsapp_alert(test_sig)
