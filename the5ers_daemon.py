"""
The5ers 24/7 Automated Monitor & Email Dispatcher Daemon
════════════════════════════════════════════════════════
Runs in the background, prevents Windows from sleeping while open,
checks MT5 status every 60 seconds, and automatically emails
wonderdock.support@gmail.com the moment an A+ ICT setup forms.
"""

import time
import sys
import ctypes
import logging
from datetime import datetime, timezone

from the5ers_elite_sniper import The5ersEliteSniper

class FlushingStreamHandler(logging.StreamHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

class FlushingFileHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        FlushingStreamHandler(sys.stdout),
        FlushingFileHandler("the5ers_daemon.log", encoding="utf-8")
    ]
)
log = logging.getLogger("The5ers-Daemon")

def prevent_sleep():
    """Tells Windows not to suspend/sleep while the bot is running."""
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        log.info("🛡️ Windows Sleep Prevention enabled: System will stay awake.")
    except Exception as e:
        log.warning(f"Could not set sleep prevention: {e}")

def run_daemon():
    prevent_sleep()
    bot = The5ersEliteSniper()
    if not bot.connect():
        log.error("Failed to connect to MT5. Exiting.")
        return

    log.info("🚀 The5ers Elite Daemon running. Will alert via Gmail when London/NY Kill Zones trigger...")

    try:
        while True:
            try:
                bot.run_cycle()
            except Exception as e:
                log.error(f"Error in scan cycle: {e}")

            time.sleep(60)
    except KeyboardInterrupt:
        log.info("Daemon stopped by user.")

if __name__ == "__main__":
    run_daemon()
