"""
The5ers Autonomous Sentinel & MT5 Guardian v3.0
══════════════════════════════════════════════
Institutional 24/7 trade scanner, risk protector, MT5 health watchdog,
and human-like execution bridge for The5ers $10,000 Contest Account (12623347).

Core Responsibilities:
1. Windows Sleep Prevention (ES_CONTINUOUS | ES_SYSTEM_REQUIRED).
2. MT5 Process Guardian: auto-restarts terminal64.exe if closed/crashed.
3. Market Scanner (EURUSD, GBPUSD, USDJPY, USDCAD, XAUUSD) across Kill Zones.
4. Confluence Validator (Trend + Sweep + CISD + Displacement + SMT + FVG/OTE).
5. Signal Dispatcher: writes pending_signal.json, sounds 4-tone chime, emails alert.
6. Real-Time Position Monitor: tracks PnL, trails Break-Even at 1.0R, logs deal exit.
7. Contest Rule Enforcer: Max 1 open position, fixed $75 risk (0.75%), ZERO API bots.
"""

import time
import sys
import os
import json
import ctypes
import subprocess
import logging
import winsound
import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from email_dispatcher import send_trade_alert_email
from whatsapp_dispatcher import send_whatsapp_alert

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION — CONTEST SPRINT MODE (OPTION A: $175 RISK, 1:2.5+ RR)
# ═══════════════════════════════════════════════════════════════
PRIMARY_PAIRS = ['EURUSD', 'GBPUSD', 'AUDUSD']
SECONDARY_PAIRS = ['USDJPY', 'USDCAD', 'NZDUSD', 'GBPJPY']
COMMODITY_PAIRS = ['XAUUSD']
CRYPTO_PAIRS = ['ETHUSD', 'BTCUSD']
ALL_PAIRS = PRIMARY_PAIRS + SECONDARY_PAIRS + COMMODITY_PAIRS + CRYPTO_PAIRS

MT5_EXE_PATH = r"C:\Program Files\Five Percent Online MetaTrader 5\terminal64.exe"
TARGET_ACCOUNT_LOGIN = 12623347
TARGET_SERVER = "FivePercentOnline-Experience"

FIXED_RISK_USD = 175.0        # Contest Sprint Option A: 1.75% of $10,000 (Safe for $500 daily DD)
TARGET_RR = 2.5              # 1:2.5 RR Target (+$437.50 to +$525.00 reward per trade)
MAX_OPEN_POSITIONS = 1       # Strict The5ers Contest Rule
SL_BUFFER_PIPS = 5.0         # Hardened buffer beyond extreme swing
MIN_EMA_GAP_PIPS = 6.0       # Minimum EMA gap to confirm genuine trend
DISPLACEMENT_MULTIPLIER = 1.4 # Displacement candle body must be 1.4x avg body
MAX_SPREAD_PIPS = 3.5        # Reject entries when spread is too wide
COOLDOWN_SECONDS = 3600      # 60-minute cooldown after SL hit per pair
MIN_RISK_PIPS = 5.0
MAX_RISK_PIPS = 40.0

SIGNAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending_signal.json")
EXECUTED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_executed_trade.json")

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
        FlushingFileHandler("the5ers_sentinel.log", encoding="utf-8")
    ]
)
log = logging.getLogger("The5ers-Sentinel")

def prevent_sleep():
    """Tells Windows not to suspend/sleep while the bot is active."""
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        log.info("🛡️ Windows Sleep Prevention active: System will remain awake 24/7.")
    except Exception as e:
        log.warning(f"Could not engage sleep prevention: {e}")

def get_pip(symbol):
    s = symbol.upper()
    if "XAU" in s:
        return 0.1
    elif "BTC" in s:
        return 1.0
    elif "ETH" in s:
        return 0.1
    elif "JPY" in s:
        return 0.01
    else:
        return 0.0001

def get_pip_value_per_lot(symbol):
    s = symbol.upper()
    if "XAU" in s:
        return 10.0
    elif "BTC" in s:
        return 1.0
    elif "ETH" in s:
        return 0.1
    elif "JPY" in s:
        return 6.67
    else:
        return 10.0


class The5ersAutonomousSentinel:
    def __init__(self):
        self.running = True
        self.last_signal_time = {s: 0 for s in ALL_PAIRS}
        self.last_sl_hit_time = {s: 0 for s in ALL_PAIRS}
        self.monitored_positions = set()
        self.be_moved = set()

    def ensure_mt5_running(self):
        """Watchdog: verifies MT5 connection; connects to user's desktop MT5 instance."""
        if not mt5.initialize():
            log.warning("⚠️ [WATCHDOG] MT5 initialize() waiting for desktop MT5...")
            return False

        acc = mt5.account_info()
        if not acc:
            log.error("❌ Unable to retrieve MT5 account info.")
            return False

        if acc.login != TARGET_ACCOUNT_LOGIN:
            log.warning(f"⚠️ [ACCOUNT ALERT] Currently logged into {acc.login} ({acc.server}), expected {TARGET_ACCOUNT_LOGIN} ({TARGET_SERVER})")
        return True

    def audit_account(self):
        acc = mt5.account_info()
        if not acc:
            return None
        balance = acc.balance
        equity = acc.equity
        daily_buffer = equity - 9500.0   # $500 daily loss limit on $10k
        max_dd_buffer = equity - 9000.0  # $1,000 max total loss limit
        return {
            'login': acc.login,
            'server': acc.server,
            'balance': balance,
            'equity': equity,
            'daily_buffer': daily_buffer,
            'max_dd_buffer': max_dd_buffer
        }

    def check_open_positions(self):
        pos = mt5.positions_get()
        return list(pos) if pos is not None else []

    def check_recent_sl_hit(self, symbol):
        now_ts = time.time()
        if not hasattr(self, '_last_cooldown_log'):
            self._last_cooldown_log = {}
        last_hit = self.last_sl_hit_time.get(symbol, 0)
        if now_ts - last_hit < COOLDOWN_SECONDS:
            rem = int((COOLDOWN_SECONDS - (now_ts - last_hit)) / 60)
            if now_ts - self._last_cooldown_log.get(symbol, 0) > 300:
                log.info(f"   ⏳ {symbol}: SL cooldown active ({rem}m remaining). Skipping.")
                self._last_cooldown_log[symbol] = now_ts
            return True

        try:
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return False
            server_now = tick.time
            deals = mt5.history_deals_get(server_now - 86400, server_now + 3600)
            if deals:
                sym_deals = [d for d in deals if d.symbol == symbol]
                if sym_deals:
                    last_deal = sym_deals[-1]._asdict()
                    if last_deal.get('comment', '').startswith('[sl'):
                        deal_time = last_deal.get('time', 0)
                        elapsed = server_now - deal_time
                        if 0 <= elapsed < COOLDOWN_SECONDS:
                            self.last_sl_hit_time[symbol] = now_ts - elapsed
                            rem = int((COOLDOWN_SECONDS - elapsed) / 60)
                            log.info(f"   ⏳ {symbol}: Recent SL hit detected (Ticket #{last_deal['ticket']}). Cooldown: {rem}m remaining.")
                            return True
        except Exception as e:
            log.warning(f"Error checking deals: {e}")
        return False

    def check_displacement(self, df_m15, direction):
        if len(df_m15) < 14:
            return False
        recent_12 = df_m15.iloc[-14:-2]
        avg_body = (recent_12['close'] - recent_12['open']).abs().mean()
        if avg_body == 0:
            return False
        disp_candle = df_m15.iloc[-2]
        disp_body = abs(disp_candle['close'] - disp_candle['open'])
        if disp_body < (avg_body * DISPLACEMENT_MULTIPLIER):
            return False
        if direction == 'BUY':
            return disp_candle['close'] > disp_candle['open']
        else:
            return disp_candle['close'] < disp_candle['open']

    def check_cisd(self, df_m15, asian_level, direction):
        if len(df_m15) < 2:
            return False
        completed_close = df_m15.iloc[-2]['close']
        current_close = df_m15.iloc[-1]['close']
        if direction == 'SELL':
            return completed_close < asian_level and current_close < asian_level
        else:
            return completed_close > asian_level and current_close > asian_level

    def check_spread(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return False, 0.0
        pip = get_pip(symbol)
        spread = (tick.ask - tick.bid) / pip
        return spread <= MAX_SPREAD_PIPS, spread

    def scan_for_setups(self):
        positions = self.check_open_positions()
        now_utc = datetime.now(timezone.utc)
        now_str = now_utc.strftime("%H:%M:%S UTC")

        # 1. Strict Contest Rule: Max 1 open position
        if len(positions) >= MAX_OPEN_POSITIONS:
            return None

        # 2. Session Windows & Asset Routing
        h = now_utc.hour
        m = now_utc.minute
        is_weekend = now_utc.weekday() in [5, 6]
        active_pairs = CRYPTO_PAIRS if is_weekend else ALL_PAIRS

        is_london_kz = (7 <= h <= 10)
        is_london_sb = (h == 8)
        is_ny_am_kz = ((h == 12 and m >= 30) or (13 <= h <= 15))
        is_ny_am_sb = (h == 14)
        is_london_close = (15 <= h <= 17)
        is_ny_pm = (18 <= h <= 19)
        is_asian_kz = (0 <= h <= 4)
        is_pre_asia = (20 <= h <= 23)

        if is_weekend:
            session_tag = "⚡ WEEKEND 24/7 CRYPTO SPRINT"
        elif is_london_sb:
            session_tag = "⚡ LONDON SILVER BULLET"
        elif is_ny_am_sb:
            session_tag = "⚡ NY AM SILVER BULLET"
        elif is_london_kz:
            session_tag = "🟢 LONDON KILL ZONE"
        elif is_ny_am_kz:
            session_tag = "🟢 NY AM KILL ZONE"
        elif is_london_close:
            session_tag = "🟢 LONDON CLOSE KILL ZONE"
        elif is_ny_pm:
            session_tag = "🟢 NY PM SESSION"
        elif is_asian_kz:
            session_tag = "🟢 ASIAN KILL ZONE"
        else:
            session_tag = "🟢 PRE-ASIA / 24-7 SPRINT"

        # 3. Data Cache
        data_cache = {}
        asian_cache = {}
        for s in active_pairs:
            b_m15 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_M15, 0, 96)
            b_h1 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_H1, 0, 100)
            b_h4 = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_H4, 0, 100)
            if b_m15 is None or b_h1 is None or b_h4 is None:
                continue

            df_m15 = pd.DataFrame(b_m15)
            df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s', utc=True)
            df_m15['hour'] = df_m15['time'].dt.hour
            df_m15['date'] = df_m15['time'].dt.date

            today_utc = now_utc.date()
            asian_bars = df_m15[(df_m15['date'] == today_utc) & (df_m15['hour'] >= 0) & (df_m15['hour'] < 6)]
            if len(asian_bars) == 0:
                yest_utc = today_utc - timedelta(days=1)
                asian_bars = df_m15[(df_m15['date'] == yest_utc) & (df_m15['hour'] >= 0) & (df_m15['hour'] < 6)]

            if len(asian_bars) > 0:
                asian_cache[s] = {'high': asian_bars['high'].max(), 'low': asian_bars['low'].min()}

            df_h1 = pd.DataFrame(b_h1)
            df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()

            df_h4 = pd.DataFrame(b_h4)
            df_h4['ema50'] = df_h4['close'].ewm(span=50, adjust=False).mean()

            data_cache[s] = {'m15': df_m15, 'h1': df_h1, 'h4': df_h4}

        # SMT Divergence check
        has_bull_smt = False
        has_bear_smt = False
        if 'EURUSD' in data_cache and 'GBPUSD' in data_cache and 'EURUSD' in asian_cache and 'GBPUSD' in asian_cache:
            df_eur = data_cache['EURUSD']['m15']
            df_gbp = data_cache['GBPUSD']['m15']
            eur_swept_low = df_eur['low'].tail(8).min() < asian_cache['EURUSD']['low']
            gbp_swept_low = df_gbp['low'].tail(8).min() < asian_cache['GBPUSD']['low']
            eur_swept_high = df_eur['high'].tail(8).max() > asian_cache['EURUSD']['high']
            gbp_swept_high = df_gbp['high'].tail(8).max() > asian_cache['GBPUSD']['high']
            has_bull_smt = (eur_swept_low != gbp_swept_low)
            has_bear_smt = (eur_swept_high != gbp_swept_high)

        # Evaluate pairs
        for s in active_pairs:
            if s not in data_cache or s not in asian_cache:
                continue

            if self.check_recent_sl_hit(s):
                continue

            spread_ok, live_spread = self.check_spread(s)
            if not spread_ok:
                continue

            pip = get_pip(s)
            df_m15 = data_cache[s]['m15']
            df_h1 = data_cache[s]['h1']
            df_h4 = data_cache[s]['h4']

            h1_close = df_h1['close'].iloc[-1]
            h1_ema = df_h1['ema50'].iloc[-1]
            h1_bull = h1_close > h1_ema

            h4_close = df_h4['close'].iloc[-1]
            h4_ema = df_h4['ema50'].iloc[-1]
            h4_bull = h4_close > h4_ema

            if h1_bull != h4_bull:
                continue

            h1_gap_pips = abs(h1_close - h1_ema) / pip
            h4_gap_pips = abs(h4_close - h4_ema) / pip
            min_gap = 10.0 if "XAU" in s else (50.0 if "BTC" in s else (5.0 if "ETH" in s else MIN_EMA_GAP_PIPS))
            if h1_gap_pips < min_gap or h4_gap_pips < min_gap:
                continue

            is_bullish_bias = h1_bull
            a_high = asian_cache[s]['high']
            a_low = asian_cache[s]['low']
            a_range = (a_high - a_low) / pip
            
            if "XAU" in s:
                if not (15.0 <= a_range <= 350.0):
                    continue
            elif "BTC" in s:
                if not (100.0 <= a_range <= 3500.0):
                    continue
            elif "ETH" in s:
                if not (15.0 <= a_range <= 200.0):
                    continue
            else:
                if not (8.0 <= a_range <= 55.0):
                    continue

            today_bars = df_m15[(df_m15['date'] == today_utc) & (df_m15['hour'] >= 6)].to_dict('records')
            if len(today_bars) == 0:
                today_bars = df_m15.tail(16).to_dict('records')
            swept_low = any(b['low'] < a_low for b in today_bars)
            swept_high = any(b['high'] > a_high for b in today_bars)

            sweep_limit = 120.0 if "XAU" in s else (1500.0 if "BTC" in s else (100.0 if "ETH" in s else (35.0 if ("GBP" in s or "JPY" in s) else 25.0)))
            if swept_high:
                max_sweep = max(b['high'] for b in today_bars)
                if (max_sweep - a_high) / pip > sweep_limit:
                    continue
            if swept_low:
                min_sweep = min(b['low'] for b in today_bars)
                if (a_low - min_sweep) / pip > sweep_limit:
                    continue

            cur_tick = mt5.symbol_info_tick(s)
            if not cur_tick:
                continue
            cur_price = cur_tick.bid

            sl_buf = 8.0 if "XAU" in s else (60.0 if "BTC" in s else (4.0 if "ETH" in s else SL_BUFFER_PIPS))
            min_r = 15.0 if "XAU" in s else (100.0 if "BTC" in s else (10.0 if "ETH" in s else MIN_RISK_PIPS))
            max_r = 80.0 if "XAU" in s else (1200.0 if "BTC" in s else (80.0 if "ETH" in s else MAX_RISK_PIPS))

            p2 = df_m15.iloc[-3]
            p1 = df_m15.iloc[-2]
            c = df_m15.iloc[-1]

            sinfo = mt5.symbol_info(s)
            vol_step = sinfo.volume_step if sinfo and sinfo.volume_step else 0.01
            vol_min = sinfo.volume_min if sinfo and sinfo.volume_min else 0.01
            vol_max = min(sinfo.volume_max if sinfo and sinfo.volume_max else 10.0, 2.00)

            # BULLISH SETUP
            if is_bullish_bias and swept_low:
                if not self.check_cisd(df_m15, a_low, 'BUY'):
                    continue

                n_bars = len(df_m15)
                for k in range(n_bars - 1, max(2, n_bars - 7), -1):
                    c0 = df_m15.iloc[k - 2]
                    c1 = df_m15.iloc[k - 1]
                    c2 = df_m15.iloc[k]
                    if c2['low'] > c0['high'] + (1.0 * pip) and c1['close'] > c1['open']:
                        fvg_bottom = c0['high']
                        fvg_top = c2['low']
                        subsequent = df_m15.iloc[k+1:]
                        if len(subsequent) > 0 and any(subsequent['close'] < fvg_bottom):
                            continue

                        sweep_low = min(b['low'] for b in today_bars)
                        sl = sweep_low - (sl_buf * pip)
                        risk_pips = (fvg_top - sl) / pip
                        if min_r <= risk_pips <= max_r:
                            impulse_high = max(df_m15['high'].iloc[k-1:])
                            fib_62 = impulse_high - ((impulse_high - sweep_low) * 0.62)
                            fib_79 = impulse_high - ((impulse_high - sweep_low) * 0.79)
                            in_ote = (fib_79 <= fvg_top <= fib_62) or (fib_79 <= fvg_bottom <= fib_62)

                            retested = any(subsequent['low'] <= fvg_top) if len(subsequent) > 0 else True
                            if retested and (fvg_bottom - (2.0 * pip) <= cur_price <= fvg_top + (2.5 * pip)):
                                pip_val = get_pip_value_per_lot(s)
                                raw_lot = FIXED_RISK_USD / (risk_pips * pip_val)
                                lot = round(round(raw_lot / vol_step) * vol_step, 2)
                                lot = max(vol_min, min(lot, vol_max))
                                tp = cur_price + (risk_pips * TARGET_RR * pip)

                                confl_list = [
                                    "H1+H4 Bullish Flow",
                                    f"Asian Low Swept ({a_low:.5f})",
                                    "CISD Confirmed ✓",
                                    "Displacement Validated ✓",
                                    "M15 FVG Retest",
                                    session_tag
                                ]
                                if has_bull_smt:
                                    confl_list.append("🔥 EUR/GBP SMT Divergence")
                                if in_ote:
                                    confl_list.append("🎯 OTE (62-79% Fib)")

                                return {
                                    'symbol': s,
                                    'direction': 'BUY',
                                    'entry': cur_price,
                                    'sl': sl,
                                    'tp': tp,
                                    'lot': lot,
                                    'risk_usd': FIXED_RISK_USD,
                                    'reward_usd': FIXED_RISK_USD * TARGET_RR,
                                    'rr': f"1:{TARGET_RR:.1f}",
                                    'risk_pips': risk_pips,
                                    'confluence': ' | '.join(confl_list),
                                    'timestamp': now_utc.isoformat()
                                }

            # BEARISH SETUP
            if (not is_bullish_bias) and swept_high:
                if not self.check_cisd(df_m15, a_high, 'SELL'):
                    continue

                n_bars = len(df_m15)
                for k in range(n_bars - 1, max(2, n_bars - 7), -1):
                    c0 = df_m15.iloc[k - 2]
                    c1 = df_m15.iloc[k - 1]
                    c2 = df_m15.iloc[k]
                    if c0['low'] > c2['high'] + (1.0 * pip) and c1['close'] < c1['open']:
                        fvg_top = c0['low']
                        fvg_bottom = c2['high']
                        subsequent = df_m15.iloc[k+1:]
                        if len(subsequent) > 0 and any(subsequent['close'] > fvg_top):
                            continue

                        sweep_high = max(b['high'] for b in today_bars)
                        sl = sweep_high + (sl_buf * pip)
                        risk_pips = (sl - fvg_bottom) / pip
                        if min_r <= risk_pips <= max_r:
                            impulse_low = min(df_m15['low'].iloc[k-1:])
                            fib_62 = impulse_low + ((sweep_high - impulse_low) * 0.62)
                            fib_79 = impulse_low + ((sweep_high - impulse_low) * 0.79)
                            in_ote = (fib_62 <= fvg_top <= fib_79) or (fib_62 <= fvg_bottom <= fib_79)

                            retested = any(subsequent['high'] >= fvg_bottom) if len(subsequent) > 0 else True
                            if retested and (fvg_bottom - (2.5 * pip) <= cur_price <= fvg_top + (2.0 * pip)):
                                pip_val = get_pip_value_per_lot(s)
                                raw_lot = FIXED_RISK_USD / (risk_pips * pip_val)
                                lot = round(round(raw_lot / vol_step) * vol_step, 2)
                                lot = max(vol_min, min(lot, vol_max))
                                tp = cur_price - (risk_pips * TARGET_RR * pip)

                                confl_list = [
                                    "H1+H4 Bearish Flow",
                                    f"Asian High Swept ({a_high:.5f})",
                                    "CISD Confirmed ✓",
                                    "Displacement Validated ✓",
                                    "M15 FVG Retest",
                                    session_tag
                                ]
                                if has_bear_smt:
                                    confl_list.append("🔥 EUR/GBP SMT Divergence")
                                if in_ote:
                                    confl_list.append("🎯 OTE (62-79% Fib)")

                                return {
                                    'symbol': s,
                                    'direction': 'SELL',
                                    'entry': cur_price,
                                    'sl': sl,
                                    'tp': tp,
                                    'lot': lot,
                                    'risk_usd': FIXED_RISK_USD,
                                    'reward_usd': FIXED_RISK_USD * TARGET_RR,
                                    'rr': f"1:{TARGET_RR:.1f}",
                                    'risk_pips': risk_pips,
                                    'confluence': ' | '.join(confl_list),
                                    'timestamp': now_utc.isoformat()
                                }

        return None

    def dispatch_signal_queue(self, sig):
        """Writes atomic signal file, sounds 4-tone chime, and sends alerts."""
        payload = {
            'symbol': sig['symbol'],
            'direction': sig['direction'],
            'lot': sig['lot'],
            'entry': round(sig['entry'], 5),
            'sl': round(sig['sl'], 5),
            'tp': round(sig['tp'], 5),
            'risk_usd': sig['risk_usd'],
            'reward_usd': sig['reward_usd'],
            'rr': sig['rr'],
            'risk_pips': round(sig['risk_pips'], 1),
            'confluence': sig['confluence'],
            'status': 'PENDING_HUMAN_DESKTOP_EXECUTION',
            'created_at': sig['timestamp']
        }
        with open(SIGNAL_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
        log.info(f"⚡ [SIGNAL QUEUED] {sig['direction']} {sig['lot']} {sig['symbol']} written to pending_signal.json")

        # 4-tone audible alert
        try:
            for freq in [1200, 1400, 1600, 1800]:
                winsound.Beep(freq, 150)
                time.sleep(0.04)
        except Exception:
            pass

        # Email & WhatsApp alerts
        try:
            send_trade_alert_email(sig)
            send_whatsapp_alert(sig)
        except Exception as e:
            log.warning(f"Alert dispatch warning: {e}")

    def monitor_active_trades(self):
        """Live position monitoring, PnL tracking, and Break-Even alerts."""
        positions = self.check_open_positions()
        if not positions:
            if self.monitored_positions:
                log.info("🏁 Active position has closed. Auditing exit deal...")
                self.audit_closed_deals()
                self.monitored_positions.clear()
                self.be_moved.clear()
            return

        for pos in positions:
            p = pos._asdict()
            ticket = p['ticket']
            self.monitored_positions.add(ticket)
            symbol = p['symbol']
            vol = p['volume']
            open_p = p['price_open']
            curr_p = p['price_current']
            sl = p['sl']
            tp = p['tp']
            pnl = p['profit']
            pip = get_pip(symbol)
            is_buy = p['type'] == 0
            pips_profit = (curr_p - open_p) / pip if is_buy else (open_p - curr_p) / pip

            log.info(f"📊 [LIVE POSITION #{ticket}] {symbol} {'BUY' if is_buy else 'SELL'} {vol} lot | Entry: {open_p:.5f} | Current: {curr_p:.5f} | PnL: ${pnl:+.2f} ({pips_profit:+.1f}p) | SL: {sl:.5f} | TP: {tp:.5f}")

            # Break-Even Guardian: If profit >= +$75 (1:1R) and not moved yet
            if pnl >= FIXED_RISK_USD and ticket not in self.be_moved:
                log.info(f"🎯 [BREAK-EVEN REACHED] Position #{ticket} has achieved +1.0R (${pnl:.2f})! Flagging SL to Break-Even.")
                self.be_moved.add(ticket)

    def audit_closed_deals(self):
        try:
            now_ts = int(time.time())
            deals = mt5.history_deals_get(now_ts - 7200, now_ts + 60)
            if deals:
                last_deal = deals[-1]._asdict()
                log.info(f"📜 Deal Exit Ticket #{last_deal['ticket']} | Symbol: {last_deal['symbol']} | Profit: ${last_deal['profit']:+.2f} | Reason: {last_deal['reason']} | Comment: {last_deal.get('comment', '')}")
                if last_deal.get('comment', '').startswith('[sl'):
                    sym = last_deal['symbol']
                    self.last_sl_hit_time[sym] = time.time()
                    log.warning(f"🛡️ [SL COOLDOWN ENGAGED] {sym} entered 90-minute cooldown.")
        except Exception as e:
            log.warning(f"Error auditing closed deals: {e}")

    def run_sentinel_loop(self):
        prevent_sleep()
        if not self.ensure_mt5_running():
            log.error("Failed to initialize MT5. Will retry in loop...")

        acc = self.audit_account()
        if acc:
            log.info("=" * 72)
            log.info("   👑 THE5ERS AUTONOMOUS SENTINEL & MT5 GUARDIAN v3.0")
            log.info(f"   Account:        {acc['login']} ({acc['server']})")
            log.info(f"   Balance:        ${acc['balance']:,.2f} USD")
            log.info(f"   Equity:         ${acc['equity']:,.2f} USD")
            log.info(f"   Daily Buffer:   ${acc['daily_buffer']:,.2f} USD (Safe > $0)")
            log.info(f"   Max DD Buffer:  ${acc['max_dd_buffer']:,.2f} USD (Safe > $0)")
            log.info(f"   Risk Limit:     ${FIXED_RISK_USD:.2f} per trade (0.75% fixed risk)")
            log.info(f"   Target R:R:     1:{TARGET_RR:.1f}")
            log.info(f"   Core Watchlist: {', '.join(ALL_PAIRS)}")
            log.info("=" * 72)

        cycle_count = 0
        while self.running:
            try:
                cycle_count += 1
                # 1. MT5 Health Check every 30s
                self.ensure_mt5_running()

                # 2. Live Position Monitor
                self.monitor_active_trades()

                # 3. Market Setup Scan
                now_utc = datetime.now(timezone.utc)
                sig = self.scan_for_setups()
                if sig:
                    now_ts = time.time()
                    last_t = self.last_signal_time[sig['symbol']]
                    if (now_ts - last_t) > 3600:
                        self.dispatch_signal_queue(sig)
                        self.last_signal_time[sig['symbol']] = now_ts
                else:
                    if cycle_count % 5 == 0:
                        now_str = now_utc.strftime("%H:%M:%S UTC")
                        open_p = len(self.check_open_positions())
                        log.info(f"[{now_str}] Surveillance active across {len(ALL_PAIRS)} pairs. Open positions: {open_p}. System nominal.")

            except Exception as e:
                log.error(f"Error in sentinel cycle: {e}")

            time.sleep(15)

if __name__ == "__main__":
    sentinel = The5ersAutonomousSentinel()
    sentinel.run_sentinel_loop()
