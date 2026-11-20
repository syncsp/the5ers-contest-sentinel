import os, json
import MetaTrader5 as mt5
from market_intelligence import get_market_intelligence

signal_path = r'C:\Users\Sunny\.gemini\antigravity\scratch\ict-trading-bot\pending_signal.json'
signal_present = os.path.exists(signal_path)
print(f'PENDING_SIGNAL_EXISTS: {signal_present}')

if signal_present:
    try:
        with open(signal_path, 'r') as f:
            print('SIGNAL_DATA:', f.read())
    except Exception as e:
        print('Error reading signal:', e)

intel = get_market_intelligence()
if intel:
    acc = intel['account']
    print(f"SILENT_MONITOR: Login={acc['login']} | Balance=${acc['balance']:.2f} | Equity=${acc['equity']:.2f} | OpenPositions={acc['open_positions']}")
    print(f"TIME_UTC: {intel['timestamp_utc']}")
    print("\n--- ACTIVE MARKET DYNAMICS ---")
    for sym, m in intel['market_data'].items():
        fvg_str = f"FVG: {m['fvg']['type']} ({m['fvg']['size_pips']}p)" if m['fvg'] else "No FVG"
        print(f"  {sym:7s} | {m['price']:10.5f} | H1: {m['h1_trend']:7s} | M15: {m['m15_trend']:7s} | {fvg_str}")
    print("\n--- UPCOMING POTENTIAL SETUPS (1:2 to 1:3 RR) ---")
    for s in intel['potential_setups']:
        print(f"  [{s['asset']}] {s['bias']} | Trigger: {s['trigger_zone']} | Target: {s['target']} | RR: {s['rr']} | Prob: {s['probability']}")
else:
    print('Failed to gather market intelligence.')
