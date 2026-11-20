"""
The5ers Elite Institutional Sniper Bot v2.0 — Post-Mortem Hardened
══════════════════════════════════════════════════════════════════
Root-Cause Fixes Applied from GBPUSD SL Hit (Ticket #17621324):

PROBLEM 1 — H1 vs H4 Trend Conflict Was NOT Filtered:
  At trade entry, H4 EMA50 was BEARISH (close 1.316 vs EMA 1.324 = 71 pips gap),
  but H1 EMA50 was flipping between BULL/BEAR with only 1.4 pips gap.
  The old code accepted the trade because H1 happened to be below EMA50
  at that specific scan, but the H1 trend was ambiguous.
  FIX: Require minimum 8-pip EMA gap on H1 AND H4 to confirm genuine
  institutional trend alignment instead of noise oscillation.

PROBLEM 2 — No MSS (Market Structure Shift) Displacement Validation:
  The bot entered on a sweep + FVG without confirming an impulsive
  displacement candle that breaks structure. Without displacement,
  the sweep was just an equal-high retest, not a genuine reversal.
  FIX: Require a displacement candle (body > 1.5× average body of last
  12 M15 candles) that closes through the structure after the sweep.

PROBLEM 3 — CISD Invalidation Not Checked:
  The bot entered SELL at 1.31543 while price was still holding above the
  Asian High (1.31537). A proper bearish CISD requires the candle body to
  close BELOW the opening price of the first bullish candle in the sweep
  sequence. Price never confirmed this — it was still in distribution, not
  confirmed reversal.
  FIX: Add candle-body-close CISD validation: for bearish, require the
  current M15 close < Asian High; for bullish, require close > Asian Low.

PROBLEM 4 — SL Too Tight (3.5 pips above sweep high):
  The sweep high was 1.31584, so SL at 1.31584 + 0.00035 = 1.31619.
  But the actual SL was 1.31645. Market ran to 1.31686 — a secondary
  liquidity sweep above the first sweep high.
  FIX: Increase SL buffer from 3.5 pips to 5.0 pips above/below the
  extreme swing, to account for secondary stop hunts.

PROBLEM 5 — No Spread Filter During High-Volatility Transition:
  London-to-NY transition (11:00-12:30 UTC) often widens spreads and
  creates false FVG/displacement patterns.
  FIX: Add spread filter — reject entries when live spread > 2.5 pips on
  majors.

PROBLEM 6 — No Consecutive-Loss Cooldown:
  After an SL hit, re-entering immediately in the same session on the same
  pair carries elevated risk (same narrative may be invalid).
  FIX: Block re-entry on the same pair for 90 minutes after an SL hit.
"""

import time
import sys
import winsound
import logging
import warnings
warnings.filterwarnings("ignore")

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from email_dispatcher import send_trade_alert_email
from whatsapp_dispatcher import send_whatsapp_alert

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════
PRIMARY_PAIRS = ['EURUSD', 'GBPUSD']
SECONDARY_PAIRS = ['USDJPY', 'USDCAD']
GOLD_PAIRS = ['XAUUSD']
ALL_PAIRS = PRIMARY_PAIRS + SECONDARY_PAIRS + GOLD_PAIRS

FIXED_RISK_USD = 75.0        # 0.75% of $10,000
TARGET_RR = 1.0              # 1:1.0 RR
MAX_OPEN_POSITIONS = 1       # The5ers Contest Rule
AUTO_EXECUTE = False         # Disabled: The5ers contest strictly prohibits EAs/bots via API
SL_BUFFER_PIPS = 5.0         # v2: increased from 3.5 to 5.0 pips
MIN_EMA_GAP_PIPS = 8.0       # v2: minimum EMA gap to confirm genuine trend (not noise)
DISPLACEMENT_MULTIPLIER = 1.5 # v2: displacement candle body must be 1.5x avg body
MAX_SPREAD_PIPS = 2.5        # v2: reject entries when spread is too wide
COOLDOWN_SECONDS = 5400      # v2: 90-minute cooldown after SL hit per pair
MIN_RISK_PIPS = 8.0
MAX_RISK_PIPS = 25.0         # v2: widened from 22.0 to 25.0 to accommodate larger SL buffer

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
        FlushingFileHandler("the5ers_elite.log", encoding="utf-8")
    ]
)
log = logging.getLogger("The5ers-Elite")

def get_pip(symbol):
    if "XAU" in symbol.upper():
        return 0.1
    return 0.01 if "JPY" in symbol.upper() else 0.0001

def get_pip_value_per_lot(symbol):
    """Returns approximate USD value per pip per 1.0 standard lot."""
    s = symbol.upper()
    if "XAU" in s:
        return 10.0       # $10 per 0.1 pip ($100 per $1.00 move per 1.0 lot)
    elif "JPY" in s:
        return 6.67       # approximate for JPY crosses
    else:
        return 10.0       # standard for EUR, GBP, AUD, CAD crosses


class The5ersEliteSniper:
    def __init__(self):
        self.running = True
        self.last_signal_time = {}
        self.last_sl_hit_time = {}   # v2: per-pair cooldown tracker

    def connect(self):
        if not mt5.initialize():
            log.error(f"MT5 Init Failed: {mt5.last_error()}")
            return False

        account = mt5.account_info()
        log.info("=" * 72)
        log.info("   👑 THE5ERS ELITE ICT SNIPER v2.0 (POST-MORTEM HARDENED)")
        log.info(f"   Account:        {account.login} ({account.server})")
        log.info(f"   Balance:        ${account.balance:,.2f} USD")
        log.info(f"   Equity:         ${account.equity:,.2f} USD")
        log.info(f"   Risk Limit:     ${FIXED_RISK_USD:.2f} per trade (0.75% fixed risk)")
        log.info(f"   Target R:R:     1:{TARGET_RR:.1f}")
        log.info(f"   SL Buffer:      {SL_BUFFER_PIPS} pips (v2 hardened)")
        log.info(f"   EMA Gap Filter: {MIN_EMA_GAP_PIPS} pips minimum")
        log.info(f"   Spread Filter:  {MAX_SPREAD_PIPS} pips maximum")
        log.info(f"   Core Watchlist: {', '.join(ALL_PAIRS)}")
        log.info("   Confluence:     Dual-Trend + Judas Sweep + CISD + Displacement + SMT + OTE")
        log.info("=" * 72)

        for s in ALL_PAIRS:
            mt5.symbol_select(s, True)
            self.last_signal_time[s] = None
            self.last_sl_hit_time[s] = 0
        return True

    def check_open_positions(self):
        positions = mt5.positions_get()
        return len(positions) if positions is not None else 0

    def check_recent_sl_hit(self, symbol):
        """v2: Detect if the last closed trade on this pair was an SL hit, and enforce cooldown."""
        now_ts = time.time()
        last_hit = self.last_sl_hit_time.get(symbol, 0)
        if now_ts - last_hit < COOLDOWN_SECONDS:
            remaining = int((COOLDOWN_SECONDS - (now_ts - last_hit)) / 60)
            log.info(f"   ⏳ {symbol}: SL cooldown active — {remaining}min remaining. Skipping.")
            return True

        # Check last closed deal for this symbol using authoritative MT5 server clock
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
                            remaining = int((COOLDOWN_SECONDS - elapsed) / 60)
                            log.info(f"   ⏳ {symbol}: Recent SL hit detected (Deal #{last_deal['ticket']}). "
                                     f"Cooldown engaged: {remaining}min remaining.")
                            return True
        except Exception as e:
            log.warning(f"Error checking deals history: {e}")
        return False

    def check_smt_divergence(self, df_eur, df_gbp, asian_eur, asian_gbp):
        """
        SMT Divergence between EURUSD and GBPUSD during Kill Zones.
        - Bullish SMT: One pair breaks Asian Low, while the other FAILS to break.
        - Bearish SMT: One pair breaks Asian High, while the other FAILS to break.
        """
        eur_swept_low = df_eur['low'].tail(8).min() < asian_eur['low']
        gbp_swept_low = df_gbp['low'].tail(8).min() < asian_gbp['low']

        eur_swept_high = df_eur['high'].tail(8).max() > asian_eur['high']
        gbp_swept_high = df_gbp['high'].tail(8).max() > asian_gbp['high']

        bullish_smt = (eur_swept_low and not gbp_swept_low) or (gbp_swept_low and not eur_swept_low)
        bearish_smt = (eur_swept_high and not gbp_swept_high) or (gbp_swept_high and not eur_swept_high)

        return bullish_smt, bearish_smt

    def check_displacement(self, df_m15, direction):
        """
        v2: Validate that the market showed genuine institutional displacement
        (impulsive candle with body > 1.5× average body of last 12 M15 candles)
        in the correct direction after the sweep. Evaluates completed candles iloc[-5:-1].
        """
        if len(df_m15) < 14:
            return False
        completed = df_m15.iloc[:-1]
        avg_body = completed.tail(12)['close'].sub(completed.tail(12)['open']).abs().mean()
        if avg_body == 0:
            return False

        # Check last 4 completed candles for genuine institutional displacement
        for _, candle in completed.tail(4).iterrows():
            body = candle['close'] - candle['open']
            if abs(body) > avg_body * DISPLACEMENT_MULTIPLIER:
                if direction == 'SELL' and body < 0:
                    return True
                elif direction == 'BUY' and body > 0:
                    return True
        return False

    def check_cisd(self, df_m15, asian_level, direction):
        """
        v2: Change in State of Delivery (CISD) confirmation.
        For bearish: both the last completed M15 candle body (iloc[-2]) and current forming close (iloc[-1])
        must be BELOW the Asian High.
        For bullish: both the last completed M15 candle body (iloc[-2]) and current forming close (iloc[-1])
        must be ABOVE the Asian Low.
        This prevents entering during the sweep itself before delivery has actually flipped.
        """
        if len(df_m15) < 2:
            return False
        completed_close = df_m15.iloc[-2]['close']
        current_close = df_m15.iloc[-1]['close']
        if direction == 'SELL':
            return completed_close < asian_level and current_close < asian_level
        else:
            return completed_close > asian_level and current_close > asian_level

    def check_spread(self, symbol):
        """v2: Reject entries when the live spread is too wide (high volatility / illiquidity)."""
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return False, 0.0
        pip = get_pip(symbol)
        spread = (tick.ask - tick.bid) / pip
        ok = spread <= MAX_SPREAD_PIPS
        return ok, spread

    def scan_for_setups(self):
        # 1. Enforce The5ers contest rule: Max 1 position open
        open_pos = self.check_open_positions()
        now_utc = datetime.now(timezone.utc)
        now_str = now_utc.strftime("%H:%M:%S UTC")

        if open_pos >= MAX_OPEN_POSITIONS:
            log.info(f"[{now_str}] Position active in The5ers ({open_pos} open). Standing by (Max 1 rule enforced).")
            return None

        # 2. Check Session & Silver Bullet Timing
        h = now_utc.hour
        m = now_utc.minute

        is_london_kz = (7 <= h <= 10)
        is_london_silver_bullet = (h == 8)
        is_ny_kz = ((h == 12 and m >= 30) or (13 <= h <= 15))
        is_ny_silver_bullet = (h == 14)

        if not (is_london_kz or is_ny_kz):
            log.info(f"[{now_str}] Current time is off-session. Prime institutional windows: London (07:00-11:00 UTC) & NY (12:30-15:30 UTC).")
            return None

        session_tag = "⚡ LONDON SILVER BULLET" if is_london_silver_bullet else (
            "⚡ NY AM SILVER BULLET" if is_ny_silver_bullet else (
                "🟢 LONDON KILL ZONE" if is_london_kz else "🟢 NY KILL ZONE"
            )
        )

        # 3. Pre-fetch data for all pairs
        data_cache = {}
        asian_cache = {}
        for s in ALL_PAIRS:
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
            asian = df_m15[(df_m15['date'] == today_utc) & (df_m15['hour'] >= 0) & (df_m15['hour'] < 6)]
            if len(asian) >= 4:
                asian_cache[s] = {'high': asian['high'].max(), 'low': asian['low'].min()}

            data_cache[s] = {'m15': df_m15, 'h1': b_h1, 'h4': b_h4}

        # SMT Divergence check on EURUSD vs GBPUSD
        has_bull_smt, has_bear_smt = False, False
        if 'EURUSD' in data_cache and 'GBPUSD' in data_cache and 'EURUSD' in asian_cache and 'GBPUSD' in asian_cache:
            has_bull_smt, has_bear_smt = self.check_smt_divergence(
                data_cache['EURUSD']['m15'], data_cache['GBPUSD']['m15'],
                asian_cache['EURUSD'], asian_cache['GBPUSD']
            )

        # Heartbeat log
        eur_str = f"{data_cache['EURUSD']['m15']['close'].iloc[-1]:.5f}" if 'EURUSD' in data_cache else "N/A"
        gbp_str = f"{data_cache['GBPUSD']['m15']['close'].iloc[-1]:.5f}" if 'GBPUSD' in data_cache else "N/A"
        log.info(f"[{now_str}] {session_tag} Active Scan | EURUSD: {eur_str} | GBPUSD: {gbp_str} | SMT Bull:{has_bull_smt} Bear:{has_bear_smt} | Open Pos: {open_pos}")

        # 4. Scan each pair for full confluence
        for s in ALL_PAIRS:
            if s not in data_cache or s not in asian_cache:
                continue

            # v2: Per-pair cooldown after SL hit
            if self.check_recent_sl_hit(s):
                continue

            pip = get_pip(s)
            df_m15 = data_cache[s]['m15']
            b_h1 = data_cache[s]['h1']
            b_h4 = data_cache[s]['h4']

            # v2: Spread filter
            spread_ok, spread_val = self.check_spread(s)
            if not spread_ok:
                log.info(f"   ⚠️ {s}: Spread too wide ({spread_val:.1f} pips > {MAX_SPREAD_PIPS} limit). Skipping.")
                continue

            # Dual-Trend Check (H1 EMA 50 & H4 EMA 50)
            df_h1 = pd.DataFrame(b_h1)
            df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()
            h1_close = df_h1['close'].iloc[-1]
            h1_ema = df_h1['ema50'].iloc[-1]
            h1_bull = h1_close > h1_ema

            df_h4 = pd.DataFrame(b_h4)
            df_h4['ema50'] = df_h4['close'].ewm(span=50, adjust=False).mean()
            h4_close = df_h4['close'].iloc[-1]
            h4_ema = df_h4['ema50'].iloc[-1]
            h4_bull = h4_close > h4_ema

            # v2: Reject if higher timeframes contradict
            if h1_bull != h4_bull:
                continue

            # v2: CRITICAL FIX — Require minimum EMA gap to confirm genuine trend
            h1_gap_pips = abs(h1_close - h1_ema) / pip
            h4_gap_pips = abs(h4_close - h4_ema) / pip
            if h1_gap_pips < MIN_EMA_GAP_PIPS:
                log.info(f"   ⚠️ {s}: H1 EMA gap too tight ({h1_gap_pips:.1f}p < {MIN_EMA_GAP_PIPS}p). Trend ambiguous. Skipping.")
                continue
            if h4_gap_pips < MIN_EMA_GAP_PIPS:
                log.info(f"   ⚠️ {s}: H4 EMA gap too tight ({h4_gap_pips:.1f}p < {MIN_EMA_GAP_PIPS}p). Trend ambiguous. Skipping.")
                continue

            is_bullish_bias = h1_bull

            a_high = asian_cache[s]['high']
            a_low = asian_cache[s]['low']
            a_range = (a_high - a_low) / pip
            if not (10.0 <= a_range <= 45.0):
                continue

            # Check sweeps in last 8 candles
            kz_bars = df_m15.tail(8).to_dict('records')
            swept_low = any(b['low'] < a_low for b in kz_bars)
            swept_high = any(b['high'] > a_high for b in kz_bars)

            # v2: Reject over-extended sweeps (> 20 pips beyond Asian boundary)
            if swept_high:
                max_sweep = max(b['high'] for b in kz_bars)
                if (max_sweep - a_high) / pip > 20.0:
                    log.info(f"   ⚠️ {s}: Sweep over-extended ({((max_sweep - a_high)/pip):.1f}p > 20p). Chasing. Skipping.")
                    continue
            if swept_low:
                min_sweep = min(b['low'] for b in kz_bars)
                if (a_low - min_sweep) / pip > 20.0:
                    log.info(f"   ⚠️ {s}: Sweep over-extended ({((a_low - min_sweep)/pip):.1f}p > 20p). Chasing. Skipping.")
                    continue

            cur_tick = mt5.symbol_info_tick(s)
            if not cur_tick:
                continue
            cur_price = cur_tick.bid

            p2 = df_m15.iloc[-3]
            p1 = df_m15.iloc[-2]
            c = df_m15.iloc[-1]

            # ─────────────────────────────────────────────────────────────
            # BULLISH A+ SETUP
            # ─────────────────────────────────────────────────────────────
            if is_bullish_bias and swept_low and p1['close'] > p1['open']:
                # v2: Check CISD — candle body must close ABOVE Asian Low
                if not self.check_cisd(df_m15, a_low, 'BUY'):
                    continue

                # v2: Check Displacement — require impulsive bullish candle
                if not self.check_displacement(df_m15, 'BUY'):
                    continue

                if c['low'] > p2['high'] + (1.2 * pip):
                    fvg_top = c['low']
                    fvg_bottom = p2['high']
                    sweep_low = min(b['low'] for b in kz_bars)
                    sl = sweep_low - (SL_BUFFER_PIPS * pip)
                    risk_pips = (fvg_top - sl) / pip

                    if MIN_RISK_PIPS <= risk_pips <= MAX_RISK_PIPS:
                        # OTE Check: 62% - 79% Fibonacci retracement
                        impulse_high = c['high']
                        fib_62 = impulse_high - ((impulse_high - sweep_low) * 0.62)
                        fib_79 = impulse_high - ((impulse_high - sweep_low) * 0.79)
                        in_ote = (fib_79 <= fvg_top <= fib_62) or (fib_79 <= fvg_bottom <= fib_62)

                        if fvg_bottom <= cur_price <= fvg_top + (2.0 * pip):
                            pip_val = get_pip_value_per_lot(s)
                            lot = round(FIXED_RISK_USD / (risk_pips * pip_val), 2)
                            lot = max(0.01, min(lot, 1.00))
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

                            log.info(f"   🎯 {s} BUY SIGNAL — Entry: {cur_price:.5f} | SL: {sl:.5f} | TP: {tp:.5f} | Lot: {lot} | Confluence: {len(confl_list)} layers")

                            return {
                                'symbol': s,
                                'direction': 'BUY',
                                'lot': lot,
                                'entry': cur_price,
                                'sl': sl,
                                'tp': tp,
                                'risk_usd': FIXED_RISK_USD,
                                'reward_usd': FIXED_RISK_USD * TARGET_RR,
                                'rr': f'1:{TARGET_RR:.1f}',
                                'confluence': " + ".join(confl_list)
                            }

            # ─────────────────────────────────────────────────────────────
            # BEARISH A+ SETUP
            # ─────────────────────────────────────────────────────────────
            elif (not is_bullish_bias) and swept_high and p1['close'] < p1['open']:
                # v2: Check CISD — candle body must close BELOW Asian High
                if not self.check_cisd(df_m15, a_high, 'SELL'):
                    continue

                # v2: Check Displacement — require impulsive bearish candle
                if not self.check_displacement(df_m15, 'SELL'):
                    continue

                if c['high'] < p2['low'] - (1.2 * pip):
                    fvg_bottom = c['high']
                    fvg_top = p2['low']
                    sweep_high = max(b['high'] for b in kz_bars)
                    sl = sweep_high + (SL_BUFFER_PIPS * pip)
                    risk_pips = (sl - fvg_bottom) / pip

                    if MIN_RISK_PIPS <= risk_pips <= MAX_RISK_PIPS:
                        impulse_low = c['low']
                        fib_62 = impulse_low + ((sweep_high - impulse_low) * 0.62)
                        fib_79 = impulse_low + ((sweep_high - impulse_low) * 0.79)
                        in_ote = (fib_62 <= fvg_bottom <= fib_79) or (fib_62 <= fvg_top <= fib_79)

                        if fvg_bottom - (2.0 * pip) <= cur_price <= fvg_top:
                            pip_val = get_pip_value_per_lot(s)
                            lot = round(FIXED_RISK_USD / (risk_pips * pip_val), 2)
                            lot = max(0.01, min(lot, 1.00))
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

                            log.info(f"   🎯 {s} SELL SIGNAL — Entry: {cur_price:.5f} | SL: {sl:.5f} | TP: {tp:.5f} | Lot: {lot} | Confluence: {len(confl_list)} layers")

                            return {
                                'symbol': s,
                                'direction': 'SELL',
                                'lot': lot,
                                'entry': cur_price,
                                'sl': sl,
                                'tp': tp,
                                'risk_usd': FIXED_RISK_USD,
                                'reward_usd': FIXED_RISK_USD * TARGET_RR,
                                'rr': f'1:{TARGET_RR:.1f}',
                                'confluence': " + ".join(confl_list)
                            }

        return None

    def execute_order(self, sig):
        """
        Executes institutional order authoritatively on MT5 broker server.
        Strictly enforces:
        1. Single position limit for The5ers ($10k Contest rule)
        2. Daily loss buffer protection ($500 daily limit)
        3. Exact fixed risk ($75.00 / 0.75%) lot sizing
        4. Hard server-side SL and TP attachments
        """
        if not AUTO_EXECUTE:
            log.info("ℹ️ AUTO_EXECUTE is disabled. Signal alert only.")
            sig['executed'] = False
            return False

        # 1. Enforce The5ers Maximum 1 Position Rule
        positions = mt5.positions_get()
        if positions is not None and len(positions) >= MAX_OPEN_POSITIONS:
            log.warning(f"⚠️ [THE5ERS RULE ENFORCEMENT] Already {len(positions)} active position! Blocking execution to protect account.")
            sig['executed'] = False
            sig['exec_error'] = "The5ers 1-Position Limit Active"
            return False

        # 2. Enforce Daily Loss Circuit Breaker
        acc = mt5.account_info()
        if acc:
            if acc.equity <= 9500.0 or (acc.equity - acc.balance) <= -350.0:
                log.warning(f"⚠️ [CIRCUIT BREAKER] Account equity (${acc.equity:.2f}) near daily limit. Blocking execution.")
                sig['executed'] = False
                sig['exec_error'] = "Daily Loss Circuit Breaker Active"
                return False

        # 3. Retrieve Live Tick & Precision Digits
        symbol = sig['symbol']
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if not tick or not info:
            log.error(f"❌ Failed to get symbol tick or info for {symbol}")
            sig['executed'] = False
            sig['exec_error'] = "Tick Data Unavailable"
            return False

        digits = info.digits
        is_buy = sig['direction'] == 'BUY'
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        price = round(tick.ask if is_buy else tick.bid, digits)
        sl = round(sig['sl'], digits)
        tp = round(sig['tp'], digits)
        lot = float(sig['lot'])

        # Filling mode detection
        filling_mode = mt5.ORDER_FILLING_IOC if (info.filling_mode & 2) else mt5.ORDER_FILLING_FOK

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 25,
            "magic": 20261119,
            "comment": "The5ers_Elite_Auto",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode
        }

        log.info(f"⚡ EXECUTING MT5 ORDER: {sig['direction']} {lot} {symbol} @ {price} | SL: {sl} | TP: {tp}")
        result = mt5.order_send(request)

        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            log.info(f"🚀 AUTO-EXECUTION CONFIRMED! Order #{result.order} | Fill Price: {result.price} | Volume: {result.volume}")
            sig['order_ticket'] = result.order
            sig['executed'] = True
            sig['fill_price'] = result.price
            return True
        else:
            err_msg = f"Retcode {result.retcode}: {result.comment}" if result else "None returned"
            log.error(f"❌ MT5 order_send rejected: {err_msg}")
            sig['executed'] = False
            sig['exec_error'] = err_msg
            return False

    def dispatch_alert(self, sig):
        # 1. Audible local chime
        try:
            for _ in range(4):
                winsound.Beep(1400, 200)
                time.sleep(0.08)
        except Exception:
            pass

        # 2. Terminal banner
        status_txt = f"🚀 AUTO-EXECUTED ON MT5 (Ticket #{sig.get('order_ticket', 'N/A')})" if sig.get('executed') else "⚠️ SIGNAL ONLY (NOT EXECUTED)"
        print("\n" + "🔥" * 45)
        print("   👑 ELITE A+ INSTITUTIONAL TRADE FOR THE5ERS! 👑")
        print("🔥" * 45)
        print(f"Status:      {status_txt}")
        print(f"Pair:        {sig['symbol']}")
        print(f"Direction:   {sig['direction']}")
        print(f"Lot Size:    {sig['lot']}")
        print(f"Entry:       {sig['entry']:.5f}")
        print(f"Stop Loss:   {sig['sl']:.5f}")
        print(f"Take Profit: {sig['tp']:.5f}")
        print(f"Risk Amount: ${sig['risk_usd']:.2f} USD (0.75%)")
        print(f"Reward:      ${sig['reward_usd']:.2f} USD (R:R {sig['rr']})")
        print(f"Confluence:  {sig['confluence']}")
        print("🔥" * 45 + "\n")

        # 3. Instant Email to wonderdock.support@gmail.com
        log.info(f"📧 Dispatching trade alert to wonderdock.support@gmail.com...")
        send_trade_alert_email(sig)

        # 4. Instant WhatsApp Alert
        log.info(f"📱 Dispatching trade alert to WhatsApp...")
        send_whatsapp_alert(sig)

    def run_cycle(self):
        sig = self.scan_for_setups()
        if sig:
            now_ts = time.time()
            last_t = self.last_signal_time[sig['symbol']]
            if last_t is None or (now_ts - last_t) > 3600:
                # 1. Authoritatively execute live order on MT5 broker server!
                self.execute_order(sig)
                # 2. Dispatch multi-channel confirmations (email, whatsapp, audio, terminal)
                self.dispatch_alert(sig)
                self.last_signal_time[sig['symbol']] = now_ts

if __name__ == "__main__":
    bot = The5ersEliteSniper()
    if bot.connect():
        bot.run_cycle()
        mt5.shutdown()
