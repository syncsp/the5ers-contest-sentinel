"""
ICT Market Structure & Analysis Engine
Implements: Fair Value Gaps, Order Blocks, Liquidity Sweeps,
            Market Structure Shifts, Swing Points
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Bias(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class FVGType(Enum):
    BULLISH = "bullish"   # Price gap up (buy signal)
    BEARISH = "bearish"   # Price gap down (sell signal)


class OBType(Enum):
    BULLISH = "bullish"   # Last bearish candle before impulse up
    BEARISH = "bearish"   # Last bullish candle before impulse down


@dataclass
class SwingPoint:
    index: int
    price: float
    is_high: bool
    timestamp: pd.Timestamp


@dataclass
class FairValueGap:
    type: FVGType
    high: float           # Upper boundary
    low: float            # Lower boundary
    midpoint: float       # 50% of FVG (optimal entry)
    candle_index: int
    timestamp: pd.Timestamp
    filled: bool = False
    tested: bool = False


@dataclass
class OrderBlock:
    type: OBType
    high: float
    low: float
    midpoint: float
    candle_index: int
    timestamp: pd.Timestamp
    mitigated: bool = False


@dataclass
class LiquidityLevel:
    price: float
    type: str             # "buy_side" or "sell_side"
    touch_count: int
    swept: bool = False
    timestamps: list = field(default_factory=list)


@dataclass
class MarketStructure:
    bias: Bias
    last_bos_price: Optional[float] = None
    last_bos_index: Optional[int] = None
    swing_highs: list = field(default_factory=list)
    swing_lows: list = field(default_factory=list)


@dataclass
class TradeSetup:
    symbol: str
    direction: str        # "BUY" or "SELL"
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    confidence: float     # 0-100
    reason: str
    timeframe: str
    timestamp: pd.Timestamp


def find_swing_points(df: pd.DataFrame, lookback: int = 5) -> list[SwingPoint]:
    """Detect swing highs and swing lows using fractal-based detection."""
    swings = []
    high = df["high"].values
    low = df["low"].values
    timestamps = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df["time"])

    for i in range(lookback, len(df) - lookback):
        # Swing High: higher than all surrounding candles
        if high[i] == max(high[i - lookback : i + lookback + 1]):
            swings.append(SwingPoint(
                index=i, price=high[i], is_high=True, timestamp=timestamps[i]
            ))
        # Swing Low: lower than all surrounding candles
        if low[i] == min(low[i - lookback : i + lookback + 1]):
            swings.append(SwingPoint(
                index=i, price=low[i], is_high=False, timestamp=timestamps[i]
            ))

    return swings


def detect_market_structure(df: pd.DataFrame, lookback: int = 50, swing_lb: int = 5) -> MarketStructure:
    """
    Determine market bias via Break of Structure (BOS) and
    Change of Character (CHoCH).
    
    Bullish: Higher Highs + Higher Lows
    Bearish: Lower Highs + Lower Lows
    """
    swings = find_swing_points(df.tail(lookback), swing_lb)
    highs = [s for s in swings if s.is_high]
    lows = [s for s in swings if not s.is_high]

    structure = MarketStructure(
        bias=Bias.NEUTRAL,
        swing_highs=highs,
        swing_lows=lows,
    )

    if len(highs) < 2 or len(lows) < 2:
        return structure

    # Check last two swing highs/lows for structure
    last_hh = highs[-1].price > highs[-2].price
    last_hl = lows[-1].price > lows[-2].price
    last_lh = highs[-1].price < highs[-2].price
    last_ll = lows[-1].price < lows[-2].price

    if last_hh and last_hl:
        structure.bias = Bias.BULLISH
        structure.last_bos_price = highs[-2].price  # Previous high that was broken
        structure.last_bos_index = highs[-1].index
    elif last_lh and last_ll:
        structure.bias = Bias.BEARISH
        structure.last_bos_price = lows[-2].price   # Previous low that was broken
        structure.last_bos_index = lows[-1].index
    else:
        # Check for CHoCH (Change of Character)
        if last_hh and last_ll:
            structure.bias = Bias.BULLISH  # CHoCH to bullish
        elif last_lh and last_hl:
            structure.bias = Bias.BEARISH  # CHoCH to bearish

    return structure


def detect_fvg(df: pd.DataFrame, min_size_pips: float = 3.0, pip_size: float = 0.0001, max_age: int = 50) -> list[FairValueGap]:
    """
    Detect Fair Value Gaps (imbalances) in price action.
    
    Bullish FVG: candle[i-1].high < candle[i+1].low  (gap up)
    Bearish FVG: candle[i-1].low > candle[i+1].high  (gap down)
    """
    fvgs = []
    data = df.tail(max_age + 2)
    high = data["high"].values
    low = data["low"].values
    timestamps = data.index if isinstance(data.index, pd.DatetimeIndex) else pd.to_datetime(data["time"])

    for i in range(1, len(data) - 1):
        # Bullish FVG
        if low[i + 1] > high[i - 1]:
            gap_size = (low[i + 1] - high[i - 1]) / pip_size
            if gap_size >= min_size_pips:
                fvg = FairValueGap(
                    type=FVGType.BULLISH,
                    high=low[i + 1],
                    low=high[i - 1],
                    midpoint=(low[i + 1] + high[i - 1]) / 2,
                    candle_index=i,
                    timestamp=timestamps[i],
                )
                # Check if FVG has been filled
                remaining = data.iloc[i + 2:]
                if len(remaining) > 0 and remaining["low"].min() <= fvg.low:
                    fvg.filled = True
                if len(remaining) > 0 and remaining["low"].min() <= fvg.midpoint:
                    fvg.tested = True
                fvgs.append(fvg)

        # Bearish FVG
        if high[i + 1] < low[i - 1]:
            gap_size = (low[i - 1] - high[i + 1]) / pip_size
            if gap_size >= min_size_pips:
                fvg = FairValueGap(
                    type=FVGType.BEARISH,
                    high=low[i - 1],
                    low=high[i + 1],
                    midpoint=(low[i - 1] + high[i + 1]) / 2,
                    candle_index=i,
                    timestamp=timestamps[i],
                )
                remaining = data.iloc[i + 2:]
                if len(remaining) > 0 and remaining["high"].max() >= fvg.high:
                    fvg.filled = True
                if len(remaining) > 0 and remaining["high"].max() >= fvg.midpoint:
                    fvg.tested = True
                fvgs.append(fvg)

    return fvgs


def detect_order_blocks(df: pd.DataFrame, lookback: int = 20, min_body_ratio: float = 0.5) -> list[OrderBlock]:
    """
    Detect Order Blocks (institutional supply/demand zones).
    
    Bullish OB: Last bearish candle before a strong bullish impulse
    Bearish OB: Last bullish candle before a strong bearish impulse
    """
    obs = []
    data = df.tail(lookback + 5)
    open_ = data["open"].values
    high = data["high"].values
    low = data["low"].values
    close = data["close"].values
    timestamps = data.index if isinstance(data.index, pd.DatetimeIndex) else pd.to_datetime(data["time"])

    for i in range(1, len(data) - 2):
        candle_range = high[i] - low[i]
        if candle_range == 0:
            continue
        body = abs(close[i] - open_[i])
        body_ratio = body / candle_range

        if body_ratio < min_body_ratio:
            continue

        is_bearish = close[i] < open_[i]
        is_bullish = close[i] > open_[i]

        # Check for strong move after this candle
        next_body = abs(close[i + 1] - open_[i + 1])
        next_range = high[i + 1] - low[i + 1]

        if next_range == 0:
            continue

        # Bullish OB: bearish candle followed by strong bullish move
        if is_bearish and close[i + 1] > open_[i + 1]:
            if next_body > body * 1.5:  # Next candle is 1.5x bigger
                obs.append(OrderBlock(
                    type=OBType.BULLISH,
                    high=open_[i],     # OB high = bearish candle open
                    low=low[i],        # OB low = bearish candle low
                    midpoint=(open_[i] + low[i]) / 2,
                    candle_index=i,
                    timestamp=timestamps[i],
                ))

        # Bearish OB: bullish candle followed by strong bearish move
        if is_bullish and close[i + 1] < open_[i + 1]:
            if next_body > body * 1.5:
                obs.append(OrderBlock(
                    type=OBType.BEARISH,
                    high=high[i],      # OB high = bullish candle high
                    low=open_[i],      # OB low = bullish candle open
                    midpoint=(high[i] + open_[i]) / 2,
                    candle_index=i,
                    timestamp=timestamps[i],
                ))

    # Check mitigation
    current_price_high = data["high"].iloc[-1]
    current_price_low = data["low"].iloc[-1]
    for ob in obs:
        after = data.iloc[ob.candle_index + 2:]
        if ob.type == OBType.BULLISH and len(after) > 0:
            if after["low"].min() < ob.low:
                ob.mitigated = True
        elif ob.type == OBType.BEARISH and len(after) > 0:
            if after["high"].max() > ob.high:
                ob.mitigated = True

    return obs


def detect_liquidity(df: pd.DataFrame, threshold_pips: float = 3.0, pip_size: float = 0.0001) -> list[LiquidityLevel]:
    """
    Detect liquidity pools (equal highs/lows where stops are resting).
    """
    levels = []
    swings = find_swing_points(df, lookback=5)
    highs = [s for s in swings if s.is_high]
    lows = [s for s in swings if not s.is_high]
    threshold = threshold_pips * pip_size

    # Find equal highs (buy-side liquidity)
    for i in range(len(highs)):
        touches = [highs[i]]
        for j in range(i + 1, len(highs)):
            if abs(highs[j].price - highs[i].price) <= threshold:
                touches.append(highs[j])
        if len(touches) >= 2:
            avg_price = sum(t.price for t in touches) / len(touches)
            if not any(abs(l.price - avg_price) <= threshold and l.type == "buy_side" for l in levels):
                levels.append(LiquidityLevel(
                    price=avg_price,
                    type="buy_side",
                    touch_count=len(touches),
                    timestamps=[t.timestamp for t in touches],
                ))

    # Find equal lows (sell-side liquidity)
    for i in range(len(lows)):
        touches = [lows[i]]
        for j in range(i + 1, len(lows)):
            if abs(lows[j].price - lows[i].price) <= threshold:
                touches.append(lows[j])
        if len(touches) >= 2:
            avg_price = sum(t.price for t in touches) / len(touches)
            if not any(abs(l.price - avg_price) <= threshold and l.type == "sell_side" for l in levels):
                levels.append(LiquidityLevel(
                    price=avg_price,
                    type="sell_side",
                    touch_count=len(touches),
                    timestamps=[t.timestamp for t in touches],
                ))

    # Check if swept
    current_high = df["high"].iloc[-1]
    current_low = df["low"].iloc[-1]
    for level in levels:
        if level.type == "buy_side" and current_high > level.price:
            level.swept = True
        elif level.type == "sell_side" and current_low < level.price:
            level.swept = True

    return levels


def get_pip_size(symbol: str) -> float:
    """Return pip size for a symbol."""
    symbol = symbol.upper()
    if "JPY" in symbol:
        return 0.01
    elif "XAU" in symbol or "GOLD" in symbol:
        return 0.1
    elif "NAS" in symbol or "US30" in symbol or "SPX" in symbol:
        return 1.0
    else:
        return 0.0001


def calculate_lot_size(
    balance: float,
    risk_percent: float,
    stop_loss_pips: float,
    pip_value: float = 10.0,  # Per standard lot for most pairs
) -> float:
    """Calculate position size based on risk management."""
    risk_amount = balance * (risk_percent / 100)
    if stop_loss_pips <= 0:
        return 0.01  # Minimum lot
    lot_size = risk_amount / (stop_loss_pips * pip_value)
    # Clamp between 0.01 and 10.0
    lot_size = max(0.01, min(10.0, round(lot_size, 2)))
    return lot_size


def score_setup(
    structure: MarketStructure,
    fvgs: list[FairValueGap],
    obs: list[OrderBlock],
    liquidity: list[LiquidityLevel],
    direction: str,
) -> float:
    """
    Score a trade setup on ICT confluence (0-100).
    Higher = more confluence = higher conviction.
    """
    score = 0.0

    # 1. Market Structure alignment (30 points max)
    if direction == "BUY" and structure.bias == Bias.BULLISH:
        score += 30
    elif direction == "SELL" and structure.bias == Bias.BEARISH:
        score += 30
    elif structure.bias == Bias.NEUTRAL:
        score += 10

    # 2. Unfilled FVG in direction (25 points max)
    relevant_fvgs = [
        f for f in fvgs
        if not f.filled
        and ((direction == "BUY" and f.type == FVGType.BULLISH)
             or (direction == "SELL" and f.type == FVGType.BEARISH))
    ]
    if relevant_fvgs:
        score += 25

    # 3. Unmitigated Order Block (25 points max)
    relevant_obs = [
        o for o in obs
        if not o.mitigated
        and ((direction == "BUY" and o.type == OBType.BULLISH)
             or (direction == "SELL" and o.type == OBType.BEARISH))
    ]
    if relevant_obs:
        score += 25

    # 4. Liquidity sweep before entry (20 points max)
    swept_levels = [l for l in liquidity if l.swept]
    if direction == "BUY" and any(l.type == "sell_side" for l in swept_levels):
        score += 20  # Sell-side liquidity swept = bullish
    elif direction == "SELL" and any(l.type == "buy_side" for l in swept_levels):
        score += 20  # Buy-side liquidity swept = bearish

    return score
