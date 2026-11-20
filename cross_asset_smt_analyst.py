"""
Cross-Asset SMT & Momentum Analysis Engine
Evaluates USDJPY, GBPJPY, USDCAD, NZDUSD, AUDUSD, GBPUSD, EURUSD
Calculates MTF EMA50 alignment, Correlation Matrix, SMT Divergences, and ICT Setups.
"""

import sys
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

SYMBOLS = ['USDJPY', 'GBPJPY', 'USDCAD', 'NZDUSD', 'AUDUSD', 'GBPUSD', 'EURUSD']

def get_pip(symbol):
    if "XAU" in symbol.upper():
        return 0.1
    return 0.01 if "JPY" in symbol.upper() else 0.0001

def fetch_data(symbol, timeframe, n_bars=120):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n_bars)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    return df

def analyze_tf_momentum(df, pip):
    if df is None or len(df) < 50:
        return {}
    current = df.iloc[-1]
    prev = df.iloc[-2]
    close = current['close']
    ema50 = current['ema50']
    ema20 = current['ema20']
    gap_pips = (close - ema50) / pip
    ema_slope_pips = (ema50 - df.iloc[-5]['ema50']) / (5 * pip)
    bias = "BULLISH" if close > ema50 else "BEARISH"
    strong_bias = "STRONG BULLISH" if (close > ema20 > ema50) else ("STRONG BEARISH" if (close < ema20 < ema50) else bias)
    
    # 5-bar ROC
    roc_pips = (close - df.iloc[-6]['close']) / pip
    
    return {
        'close': float(close),
        'ema50': float(ema50),
        'gap_pips': round(float(gap_pips), 1),
        'ema_slope_pips': round(float(ema_slope_pips), 2),
        'roc_5_pips': round(float(roc_pips), 1),
        'bias': bias,
        'detailed_bias': strong_bias
    }

def calculate_correlations():
    # Fetch M15 returns for last 96 bars (24h)
    m15_returns = {}
    h1_returns = {}
    for s in SYMBOLS:
        df_m15 = fetch_data(s, mt5.TIMEFRAME_M15, 96)
        if df_m15 is not None:
            m15_returns[s] = df_m15['close'].pct_change().dropna()
        df_h1 = fetch_data(s, mt5.TIMEFRAME_H1, 120)
        if df_h1 is not None:
            h1_returns[s] = df_h1['close'].pct_change().dropna()
            
    corr_m15 = pd.DataFrame(m15_returns).corr()
    corr_h1 = pd.DataFrame(h1_returns).corr()
    return corr_m15, corr_h1

def detect_smt_divergence(sym1, sym2, df1_m15, df2_m15, inverted=False):
    """
    Checks for SMT divergence between sym1 and sym2 over recent swing points.
    If inverted=True (e.g. USDJPY vs EURUSD), expects inverse relationship (sym1 high corresponds to sym2 low).
    """
    # Look at last 32 bars (~8 hours)
    sub1 = df1_m15.tail(32).reset_index(drop=True)
    sub2 = df2_m15.tail(32).reset_index(drop=True)
    
    pip1 = get_pip(sym1)
    pip2 = get_pip(sym2)
    
    # Find two distinct swing highs/lows in the first half vs second half
    half = 16
    h1_first, h1_second = sub1['high'].iloc[:half].max(), sub1['high'].iloc[half:].max()
    l1_first, l1_second = sub1['low'].iloc[:half].min(), sub1['low'].iloc[half:].min()
    
    h2_first, h2_second = sub2['high'].iloc[:half].max(), sub2['high'].iloc[half:].max()
    l2_first, l2_second = sub2['low'].iloc[:half].min(), sub2['low'].iloc[half:].min()
    
    smt_events = []
    
    if not inverted:
        # Correlated pairs (e.g. AUDUSD vs NZDUSD)
        # Highs: higher high in one vs lower high in another -> Bearish SMT
        sym1_higher_high = h1_second > h1_first
        sym2_higher_high = h2_second > h2_first
        if sym1_higher_high and not sym2_higher_high:
            smt_events.append({
                'type': 'BEARISH_SMT',
                'description': f"{sym1} made a Higher High ({h1_second:.5f} > {h1_first:.5f}) while {sym2} failed with a Lower High ({h2_second:.5f} < {h2_first:.5f})",
                'leader': sym1,
                'laggard': sym2
            })
        elif not sym1_higher_high and sym2_higher_high:
            smt_events.append({
                'type': 'BEARISH_SMT',
                'description': f"{sym2} made a Higher High ({h2_second:.5f} > {h2_first:.5f}) while {sym1} failed with a Lower High ({h1_second:.5f} < {h1_first:.5f})",
                'leader': sym2,
                'laggard': sym1
            })
            
        # Lows: lower low in one vs higher low in another -> Bullish SMT
        sym1_lower_low = l1_second < l1_first
        sym2_lower_low = l2_second < l2_first
        if sym1_lower_low and not sym2_lower_low:
            smt_events.append({
                'type': 'BULLISH_SMT',
                'description': f"{sym1} swept Lower Low ({l1_second:.5f} < {l1_first:.5f}) while {sym2} held a Higher Low ({l2_second:.5f} > {l2_first:.5f})",
                'leader': sym1,
                'laggard': sym2
            })
        elif not sym1_lower_low and sym2_lower_low:
            smt_events.append({
                'type': 'BULLISH_SMT',
                'description': f"{sym2} swept Lower Low ({l2_second:.5f} < {l2_first:.5f}) while {sym1} held a Higher Low ({l1_second:.5f} > {l1_first:.5f})",
                'leader': sym2,
                'laggard': sym1
            })
    else:
        # Inverted pairs (e.g. USDJPY vs EURUSD)
        # USDJPY Higher High should correspond to EURUSD Lower Low.
        sym1_higher_high = h1_second > h1_first
        sym2_lower_low = l2_second < l2_first # for EURUSD
        if sym1_higher_high and not sym2_lower_low:
            smt_events.append({
                'type': 'USD_DIVERGENCE_BEARISH_USD',
                'description': f"{sym1} pushed Higher High ({h1_second:.5f} > {h1_first:.5f}) but {sym2} did NOT push Lower Low ({l2_second:.5f} >= {l2_first:.5f}) - Dollar strength unconfirmed",
                'leader': sym1,
                'laggard': sym2
            })
        elif not sym1_higher_high and sym2_lower_low:
            smt_events.append({
                'type': 'USD_DIVERGENCE_BULLISH_USD',
                'description': f"{sym2} pushed Lower Low ({l2_second:.5f} < {l2_first:.5f}) while {sym1} failed to make Higher High ({h1_second:.5f} <= {h1_first:.5f}) - Dollar strength unconfirmed on JPY",
                'leader': sym2,
                'laggard': sym1
            })

    return smt_events

def detect_fvg_and_setups(symbol, df_m15, df_m5):
    pip = get_pip(symbol)
    setups = []
    
    # Check last 10 candles on M15 for FVGs
    for i in range(len(df_m15) - 8, len(df_m15) - 1):
        c1 = df_m15.iloc[i-1]
        c2 = df_m15.iloc[i]
        c3 = df_m15.iloc[i+1]
        
        # Bullish FVG: c1.high < c3.low
        if c3['low'] > c1['high']:
            gap = (c3['low'] - c1['high']) / pip
            if gap >= 2.0:
                current_price = df_m15.iloc[-1]['close']
                # Check if mitigated
                future_lows = df_m15['low'].iloc[i+1:]
                mitigated = any(low <= c1['high'] for low in future_lows)
                in_fvg = (current_price >= c1['high'] and current_price <= c3['low'])
                setups.append({
                    'timeframe': 'M15',
                    'type': 'BULLISH_FVG',
                    'time': str(c2['time']),
                    'top': float(c3['low']),
                    'bottom': float(c1['high']),
                    'gap_pips': round(float(gap), 1),
                    'mitigated': bool(mitigated),
                    'in_fvg_now': bool(in_fvg)
                })
                
        # Bearish FVG: c1.low > c3.high
        if c1['low'] > c3['high']:
            gap = (c1['low'] - c3['high']) / pip
            if gap >= 2.0:
                current_price = df_m15.iloc[-1]['close']
                future_highs = df_m15['high'].iloc[i+1:]
                mitigated = any(high >= c1['low'] for high in future_highs)
                in_fvg = (current_price <= c1['low'] and current_price >= c3['high'])
                setups.append({
                    'timeframe': 'M15',
                    'type': 'BEARISH_FVG',
                    'time': str(c2['time']),
                    'top': float(c1['low']),
                    'bottom': float(c3['high']),
                    'gap_pips': round(float(gap), 1),
                    'mitigated': bool(mitigated),
                    'in_fvg_now': bool(in_fvg)
                })
                
    # Also check M5 for precision
    if df_m5 is not None and len(df_m5) >= 15:
        for i in range(len(df_m5) - 10, len(df_m5) - 1):
            c1 = df_m5.iloc[i-1]
            c2 = df_m5.iloc[i]
            c3 = df_m5.iloc[i+1]
            
            if c3['low'] > c1['high']:
                gap = (c3['low'] - c1['high']) / pip
                if gap >= 1.5:
                    current_price = df_m5.iloc[-1]['close']
                    future_lows = df_m5['low'].iloc[i+1:]
                    mitigated = any(low <= c1['high'] for low in future_lows)
                    in_fvg = (current_price >= c1['high'] and current_price <= c3['low'])
                    setups.append({
                        'timeframe': 'M5',
                        'type': 'BULLISH_FVG',
                        'time': str(c2['time']),
                        'top': float(c3['low']),
                        'bottom': float(c1['high']),
                        'gap_pips': round(float(gap), 1),
                        'mitigated': bool(mitigated),
                        'in_fvg_now': bool(in_fvg)
                    })
            if c1['low'] > c3['high']:
                gap = (c1['low'] - c3['high']) / pip
                if gap >= 1.5:
                    current_price = df_m5.iloc[-1]['close']
                    future_highs = df_m5['high'].iloc[i+1:]
                    mitigated = any(high >= c1['low'] for high in future_highs)
                    in_fvg = (current_price <= c1['low'] and current_price >= c3['high'])
                    setups.append({
                        'timeframe': 'M5',
                        'type': 'BEARISH_FVG',
                        'time': str(c2['time']),
                        'top': float(c1['low']),
                        'bottom': float(c3['high']),
                        'gap_pips': round(float(gap), 1),
                        'mitigated': bool(mitigated),
                        'in_fvg_now': bool(in_fvg)
                    })
    return setups

def main():
    if not mt5.initialize():
        print("ERROR: MT5 initialize failed")
        return
        
    print(f"MT5 Connected successfully. Evaluating {len(SYMBOLS)} symbols at {datetime.now(timezone.utc)}...")
    
    # 1. Multi-Timeframe Alignment
    report = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'momentum_analysis': {},
        'smt_divergences': {},
        'fvg_setups': {},
        'yen_order_flow': {},
        'correlations_m15': {},
        'correlations_h1': {}
    }
    
    data_store = {}
    for s in SYMBOLS:
        df_h4 = fetch_data(s, mt5.TIMEFRAME_H4, 100)
        df_h1 = fetch_data(s, mt5.TIMEFRAME_H1, 100)
        df_m15 = fetch_data(s, mt5.TIMEFRAME_M15, 100)
        df_m5 = fetch_data(s, mt5.TIMEFRAME_M5, 100)
        pip = get_pip(s)
        
        data_store[s] = {'h4': df_h4, 'h1': df_h1, 'm15': df_m15, 'm5': df_m5, 'pip': pip}
        
        tick = mt5.symbol_info_tick(s)
        spread_pips = round((tick.ask - tick.bid) / pip, 1) if tick else 0.0
        
        h4_an = analyze_tf_momentum(df_h4, pip)
        h1_an = analyze_tf_momentum(df_h1, pip)
        m15_an = analyze_tf_momentum(df_m15, pip)
        
        # Alignment check
        aligned = (h4_an.get('bias') == h1_an.get('bias') == m15_an.get('bias'))
        alignment_bias = h4_an.get('bias') if aligned else "MIXED"
        
        report['momentum_analysis'][s] = {
            'bid': tick.bid if tick else 0,
            'ask': tick.ask if tick else 0,
            'spread_pips': spread_pips,
            'alignment': alignment_bias,
            'h4': h4_an,
            'h1': h1_an,
            'm15': m15_an
        }
        
        # Setups
        setups = detect_fvg_and_setups(s, df_m15, df_m5)
        report['fvg_setups'][s] = setups

    # 2. SMT Divergences
    # AUDUSD vs NZDUSD
    smt_aud_nzd = detect_smt_divergence('AUDUSD', 'NZDUSD', data_store['AUDUSD']['m15'], data_store['NZDUSD']['m15'])
    report['smt_divergences']['AUDUSD_vs_NZDUSD'] = smt_aud_nzd
    
    # USDJPY vs USDCAD
    smt_uj_ucad = detect_smt_divergence('USDJPY', 'USDCAD', data_store['USDJPY']['m15'], data_store['USDCAD']['m15'])
    report['smt_divergences']['USDJPY_vs_USDCAD'] = smt_uj_ucad
    
    # USDJPY vs EURUSD (inverted USD benchmark)
    smt_uj_eur = detect_smt_divergence('USDJPY', 'EURUSD', data_store['USDJPY']['m15'], data_store['EURUSD']['m15'], inverted=True)
    report['smt_divergences']['USDJPY_vs_EURUSD_proxyDXY'] = smt_uj_eur
    
    # GBPUSD vs GBPJPY
    smt_gu_gj = detect_smt_divergence('GBPUSD', 'GBPJPY', data_store['GBPUSD']['m15'], data_store['GBPJPY']['m15'])
    report['smt_divergences']['GBPUSD_vs_GBPJPY'] = smt_gu_gj

    # 3. Yen Order Flow
    # Compare USDJPY and GBPJPY momentum over H4, H1, M15
    uj_m15_roc = report['momentum_analysis']['USDJPY']['m15']['roc_5_pips']
    gj_m15_roc = report['momentum_analysis']['GBPJPY']['m15']['roc_5_pips']
    uj_h1_roc = report['momentum_analysis']['USDJPY']['h1']['roc_5_pips']
    gj_h1_roc = report['momentum_analysis']['GBPJPY']['h1']['roc_5_pips']
    
    report['yen_order_flow'] = {
        'USDJPY_M15_ROC_pips': uj_m15_roc,
        'GBPJPY_M15_ROC_pips': gj_m15_roc,
        'USDJPY_H1_ROC_pips': uj_h1_roc,
        'GBPJPY_H1_ROC_pips': gj_h1_roc,
        'summary': 'YEN_WEAK' if (uj_m15_roc > 0 and gj_m15_roc > 0) else ('YEN_STRONG' if (uj_m15_roc < 0 and gj_m15_roc < 0) else 'YEN_MIXED')
    }

    # 4. Correlation Matrices
    c_m15, c_h1 = calculate_correlations()
    report['correlations_m15'] = c_m15.round(2).to_dict()
    report['correlations_h1'] = c_h1.round(2).to_dict()

    out_path = r"C:\Users\Sunny\.gemini\antigravity\scratch\ict-trading-bot\cross_asset_smt_report.json"
    with open(out_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"Report written to {out_path}")

if __name__ == '__main__':
    main()
