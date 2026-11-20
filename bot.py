"""
ICT Automated Trading Bot for The5ers Contest
═══════════════════════════════════════════════
Connects to MetaTrader 5 and trades using ICT concepts:
- Market Structure (BOS/CHoCH)
- Fair Value Gaps (FVG)
- Order Blocks (OB)
- Liquidity Sweeps
- Kill Zone timing

Contest: Top 100 | Contest 261118
Risk: 1% per trade, max 2 open, max 3 trades/day
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
import sys
from datetime import datetime, timezone, timedelta

from config import (
    ACCOUNT_BALANCE, MAX_LOSS_LIMIT, DAILY_LOSS_LIMIT,
    RISK_PER_TRADE_PCT, MAX_OPEN_TRADES, MAX_TRADES_PER_DAY,
    MIN_RR_RATIO, SYMBOLS, KILL_ZONES, ACTIVE_KILL_ZONES,
    FVG_MIN_SIZE_PIPS, FVG_MAX_AGE_CANDLES,
    OB_LOOKBACK, OB_MIN_BODY_RATIO,
    MSS_LOOKBACK, SWING_LOOKBACK,
    LIQ_EQUAL_THRESHOLD_PIPS,
    HTF_TIMEFRAME, LTF_TIMEFRAME, ENTRY_TIMEFRAME,
    SCAN_INTERVAL_SECONDS,
)
from ict_engine import (
    detect_market_structure, detect_fvg, detect_order_blocks,
    detect_liquidity, score_setup, calculate_lot_size,
    get_pip_size, Bias, FVGType, OBType,
    TradeSetup,
)

# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("trading_log.txt", encoding="utf-8"),
    ],
)
log = logging.getLogger("ICT-Bot")

# MT5 timeframe mapping
TF_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


class ICTTradingBot:
    def __init__(self):
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.last_reset_date = None
        self.running = True
        self.total_pnl = 0.0

    # ───────────────────────────────────────────────────────
    # MT5 CONNECTION
    # ───────────────────────────────────────────────────────
    def connect(self) -> bool:
        """Initialize connection to MT5 terminal."""
        if not mt5.initialize():
            log.error(f"MT5 initialize failed: {mt5.last_error()}")
            return False

        info = mt5.account_info()
        if info is None:
            log.error("Failed to get account info")
            mt5.shutdown()
            return False

        log.info("═" * 60)
        log.info("   ICT TRADING BOT — The5ers Contest")
        log.info("═" * 60)
        log.info(f"  Account:  {info.login}")
        log.info(f"  Server:   {info.server}")
        log.info(f"  Balance:  {info.balance:.2f} {info.currency}")
        log.info(f"  Equity:   {info.equity:.2f} {info.currency}")
        log.info(f"  Leverage: 1:{info.leverage}")
        log.info("═" * 60)

        return True

    # ───────────────────────────────────────────────────────
    # DATA FETCHING
    # ───────────────────────────────────────────────────────
    def get_candles(self, symbol: str, timeframe: str, count: int = 200) -> pd.DataFrame | None:
        """Fetch OHLCV data from MT5."""
        tf = TF_MAP.get(timeframe)
        if tf is None:
            log.error(f"Unknown timeframe: {timeframe}")
            return None

        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            log.warning(f"No data for {symbol} {timeframe}")
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        return df

    # ───────────────────────────────────────────────────────
    # KILL ZONE CHECK
    # ───────────────────────────────────────────────────────
    def is_in_kill_zone(self) -> tuple[bool, str]:
        """Check if current time is within an active ICT kill zone (UTC)."""
        now = datetime.now(timezone.utc)
        current_time = now.strftime("%H:%M")

        for zone_name in ACTIVE_KILL_ZONES:
            zone = KILL_ZONES[zone_name]
            if zone["start"] <= current_time <= zone["end"]:
                return True, zone_name

        return False, ""

    # ───────────────────────────────────────────────────────
    # RISK CHECKS
    # ───────────────────────────────────────────────────────
    def check_risk_limits(self) -> bool:
        """Verify we haven't exceeded risk limits."""
        info = mt5.account_info()
        if info is None:
            return False

        # Reset daily counter at midnight UTC
        today = datetime.now(timezone.utc).date()
        if self.last_reset_date != today:
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.last_reset_date = today
            log.info("🔄 Daily counters reset")

        # Check max daily trades
        if self.daily_trades >= MAX_TRADES_PER_DAY:
            log.info(f"⏸  Max daily trades reached ({MAX_TRADES_PER_DAY})")
            return False

        # Check open positions
        positions = mt5.positions_total()
        if positions >= MAX_OPEN_TRADES:
            log.info(f"⏸  Max open trades reached ({MAX_OPEN_TRADES})")
            return False

        # Check total P&L vs max loss
        total_pnl = info.equity - ACCOUNT_BALANCE
        if abs(total_pnl) >= MAX_LOSS_LIMIT * 0.8:  # 80% of max loss = stop
            log.warning(f"🛑 Near max loss limit! P&L: {total_pnl:.2f}")
            return False

        # Check daily P&L
        daily_loss = info.equity - info.balance  # Unrealized
        open_positions = mt5.positions_get()
        if open_positions:
            daily_loss = sum(p.profit for p in open_positions)
        if abs(daily_loss) >= DAILY_LOSS_LIMIT * 0.8:  # 80% of daily limit
            log.warning(f"🛑 Near daily loss limit! Daily P&L: {daily_loss:.2f}")
            return False

        return True

    # ───────────────────────────────────────────────────────
    # ANALYSIS
    # ───────────────────────────────────────────────────────
    def analyze_symbol(self, symbol: str) -> TradeSetup | None:
        """
        Full ICT analysis on a symbol:
        1. HTF (H4) → Determine bias (Market Structure)
        2. LTF (M15) → Find FVGs, OBs, Liquidity
        3. Entry (M5) → Precision entry level
        """
        pip_size = get_pip_size(symbol)

        # ── Step 1: HTF Bias ──
        htf_data = self.get_candles(symbol, HTF_TIMEFRAME, 100)
        if htf_data is None or len(htf_data) < MSS_LOOKBACK:
            return None

        htf_structure = detect_market_structure(htf_data, MSS_LOOKBACK, SWING_LOOKBACK)
        if htf_structure.bias == Bias.NEUTRAL:
            return None  # No clear direction, skip

        direction = "BUY" if htf_structure.bias == Bias.BULLISH else "SELL"

        # ── Step 2: LTF Analysis ──
        ltf_data = self.get_candles(symbol, LTF_TIMEFRAME, 150)
        if ltf_data is None or len(ltf_data) < 50:
            return None

        # Confirm LTF aligns with HTF
        ltf_structure = detect_market_structure(ltf_data, MSS_LOOKBACK, SWING_LOOKBACK)
        if ltf_structure.bias != htf_structure.bias:
            return None  # No alignment = no trade

        # Find ICT elements
        fvgs = detect_fvg(ltf_data, FVG_MIN_SIZE_PIPS, pip_size, FVG_MAX_AGE_CANDLES)
        obs = detect_order_blocks(ltf_data, OB_LOOKBACK, OB_MIN_BODY_RATIO)
        liquidity = detect_liquidity(ltf_data, LIQ_EQUAL_THRESHOLD_PIPS, pip_size)

        # Score the setup
        confidence = score_setup(htf_structure, fvgs, obs, liquidity, direction)
        if confidence < 55:  # Need at least 55% confluence
            return None

        # ── Step 3: Entry Precision ──
        entry_data = self.get_candles(symbol, ENTRY_TIMEFRAME, 50)
        if entry_data is None:
            return None

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None

        current_price = tick.ask if direction == "BUY" else tick.bid

        # Find entry, SL, TP
        entry, sl, tp = self._calculate_levels(
            direction, current_price, fvgs, obs, liquidity, pip_size, symbol
        )

        if entry is None:
            return None

        # Calculate risk:reward
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        if risk == 0:
            return None
        rr = reward / risk

        if rr < MIN_RR_RATIO:
            return None

        return TradeSetup(
            symbol=symbol,
            direction=direction,
            entry=entry,
            stop_loss=sl,
            take_profit=tp,
            risk_reward=round(rr, 2),
            confidence=confidence,
            reason=self._build_reason(htf_structure, fvgs, obs, liquidity, direction),
            timeframe=LTF_TIMEFRAME,
            timestamp=pd.Timestamp.now(tz="UTC"),
        )

    def _calculate_levels(self, direction, price, fvgs, obs, liquidity, pip_size, symbol):
        """Calculate entry, stop-loss, and take-profit levels."""
        entry = price

        # Use nearest unmitigated OB or unfilled FVG for SL placement
        if direction == "BUY":
            # SL below the nearest bullish OB or FVG low
            sl_candidates = []
            for ob in obs:
                if ob.type == OBType.BULLISH and not ob.mitigated:
                    sl_candidates.append(ob.low)
            for fvg in fvgs:
                if fvg.type == FVGType.BULLISH and not fvg.filled:
                    sl_candidates.append(fvg.low)

            if sl_candidates:
                sl = min(sl_candidates) - (5 * pip_size)  # 5 pips buffer
            else:
                # Fallback: use recent swing low
                sl = price - (30 * pip_size)

            # TP at next liquidity level (buy-side) or 2x risk
            risk = abs(entry - sl)
            tp_candidates = [l.price for l in liquidity if l.type == "buy_side" and not l.swept and l.price > price]
            if tp_candidates:
                tp = min(tp_candidates)
                if abs(tp - entry) < risk * MIN_RR_RATIO:
                    tp = entry + (risk * MIN_RR_RATIO)
            else:
                tp = entry + (risk * MIN_RR_RATIO)

        else:  # SELL
            sl_candidates = []
            for ob in obs:
                if ob.type == OBType.BEARISH and not ob.mitigated:
                    sl_candidates.append(ob.high)
            for fvg in fvgs:
                if fvg.type == FVGType.BEARISH and not fvg.filled:
                    sl_candidates.append(fvg.high)

            if sl_candidates:
                sl = max(sl_candidates) + (5 * pip_size)
            else:
                sl = price + (30 * pip_size)

            risk = abs(sl - entry)
            tp_candidates = [l.price for l in liquidity if l.type == "sell_side" and not l.swept and l.price < price]
            if tp_candidates:
                tp = max(tp_candidates)
                if abs(entry - tp) < risk * MIN_RR_RATIO:
                    tp = entry - (risk * MIN_RR_RATIO)
            else:
                tp = entry - (risk * MIN_RR_RATIO)

        # Validate
        if direction == "BUY" and (sl >= entry or tp <= entry):
            return None, None, None
        if direction == "SELL" and (sl <= entry or tp >= entry):
            return None, None, None

        # Round to symbol's digits
        sym_info = mt5.symbol_info(symbol)
        digits = sym_info.digits if sym_info else 5
        entry = round(entry, digits)
        sl = round(sl, digits)
        tp = round(tp, digits)

        return entry, sl, tp

    def _build_reason(self, structure, fvgs, obs, liquidity, direction):
        """Build human-readable reason for the trade."""
        reasons = []
        reasons.append(f"HTF Bias: {structure.bias.value.upper()}")

        unfilled_fvgs = [f for f in fvgs if not f.filled and
                         ((direction == "BUY" and f.type == FVGType.BULLISH) or
                          (direction == "SELL" and f.type == FVGType.BEARISH))]
        if unfilled_fvgs:
            reasons.append(f"{len(unfilled_fvgs)} unfilled FVG(s)")

        active_obs = [o for o in obs if not o.mitigated and
                      ((direction == "BUY" and o.type == OBType.BULLISH) or
                       (direction == "SELL" and o.type == OBType.BEARISH))]
        if active_obs:
            reasons.append(f"{len(active_obs)} unmitigated OB(s)")

        swept = [l for l in liquidity if l.swept]
        if swept:
            reasons.append(f"Liquidity swept ({len(swept)} level(s))")

        return " | ".join(reasons)

    # ───────────────────────────────────────────────────────
    # TRADE EXECUTION
    # ───────────────────────────────────────────────────────
    def execute_trade(self, setup: TradeSetup) -> bool:
        """Execute a trade on MT5."""
        sym_info = mt5.symbol_info(setup.symbol)
        if sym_info is None:
            log.error(f"Symbol {setup.symbol} not found")
            return False

        if not sym_info.visible:
            if not mt5.symbol_select(setup.symbol, True):
                log.error(f"Failed to select {setup.symbol}")
                return False

        # Calculate lot size
        pip_size = get_pip_size(setup.symbol)
        sl_pips = abs(setup.entry - setup.stop_loss) / pip_size

        # Estimate pip value (approximate)
        pip_value = 10.0  # Default for standard lot
        if "JPY" in setup.symbol:
            pip_value = 7.5
        elif "XAU" in setup.symbol:
            pip_value = 1.0
        elif "NAS" in setup.symbol or "US30" in setup.symbol:
            pip_value = 1.0

        info = mt5.account_info()
        balance = info.balance if info else ACCOUNT_BALANCE

        lot = calculate_lot_size(balance, RISK_PER_TRADE_PCT, sl_pips, pip_value)

        # Check minimum volume
        lot = max(sym_info.volume_min, lot)
        lot = min(sym_info.volume_max, lot)
        # Round to volume step
        if sym_info.volume_step > 0:
            lot = round(lot / sym_info.volume_step) * sym_info.volume_step
        lot = round(lot, 2)

        tick = mt5.symbol_info_tick(setup.symbol)
        if tick is None:
            return False

        order_type = mt5.ORDER_TYPE_BUY if setup.direction == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick.ask if setup.direction == "BUY" else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": setup.symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": setup.stop_loss,
            "tp": setup.take_profit,
            "deviation": 20,  # 2 pips slippage
            "magic": 123456,
            "comment": f"ICT|{setup.confidence:.0f}%|RR:{setup.risk_reward}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None:
            log.error(f"Order send failed: {mt5.last_error()}")
            return False

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Order rejected: {result.retcode} — {result.comment}")
            # Try with FOK filling
            request["type_filling"] = mt5.ORDER_FILLING_FOK
            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                log.error(f"Order rejected (retry): {result.retcode if result else 'None'}")
                return False

        self.daily_trades += 1

        log.info("═" * 60)
        log.info(f"  ✅ TRADE EXECUTED — {setup.direction} {setup.symbol}")
        log.info(f"  Volume: {lot} lots")
        log.info(f"  Entry:  {price}")
        log.info(f"  SL:     {setup.stop_loss}")
        log.info(f"  TP:     {setup.take_profit}")
        log.info(f"  R:R:    1:{setup.risk_reward}")
        log.info(f"  Score:  {setup.confidence}%")
        log.info(f"  Reason: {setup.reason}")
        log.info(f"  Daily trades: {self.daily_trades}/{MAX_TRADES_PER_DAY}")
        log.info("═" * 60)

        return True

    # ───────────────────────────────────────────────────────
    # MAIN LOOP
    # ───────────────────────────────────────────────────────
    def run(self):
        """Main scanning and trading loop."""
        if not self.connect():
            log.error("Failed to connect to MT5. Is the terminal running?")
            return

        log.info("🚀 Bot started — scanning for ICT setups...")
        log.info(f"   Symbols: {', '.join(SYMBOLS)}")
        log.info(f"   Kill Zones: {', '.join(ACTIVE_KILL_ZONES)}")
        log.info(f"   Risk: {RISK_PER_TRADE_PCT}% per trade")
        log.info(f"   Min R:R: 1:{MIN_RR_RATIO}")

        try:
            while self.running:
                # Check kill zone
                in_kz, kz_name = self.is_in_kill_zone()
                if not in_kz:
                    now_utc = datetime.now(timezone.utc).strftime("%H:%M")
                    log.info(f"⏳ Outside kill zone ({now_utc} UTC). Waiting...")
                    time.sleep(60)
                    continue

                log.info(f"🎯 Active in {kz_name.upper()} kill zone")

                # Check risk limits
                if not self.check_risk_limits():
                    time.sleep(SCAN_INTERVAL_SECONDS)
                    continue

                # Scan all symbols
                best_setup: TradeSetup | None = None
                for symbol in SYMBOLS:
                    try:
                        setup = self.analyze_symbol(symbol)
                        if setup and (best_setup is None or setup.confidence > best_setup.confidence):
                            best_setup = setup
                    except Exception as e:
                        log.error(f"Error analyzing {symbol}: {e}")

                if best_setup:
                    log.info(f"📊 Best setup: {best_setup.direction} {best_setup.symbol} "
                             f"(Score: {best_setup.confidence}%, R:R 1:{best_setup.risk_reward})")
                    self.execute_trade(best_setup)
                else:
                    log.info("🔍 No valid ICT setups found this scan")

                # Wait before next scan
                log.info(f"⏰ Next scan in {SCAN_INTERVAL_SECONDS}s...")
                time.sleep(SCAN_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            log.info("🛑 Bot stopped by user")
        finally:
            # Log final status
            info = mt5.account_info()
            if info:
                log.info(f"Final balance: {info.balance:.2f} | Equity: {info.equity:.2f}")
            mt5.shutdown()
            log.info("MT5 connection closed")


if __name__ == "__main__":
    bot = ICTTradingBot()
    bot.run()
